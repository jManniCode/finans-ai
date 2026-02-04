import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Send, User, Bot, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import ChartRenderer from './ChartRenderer';
import ReactMarkdown from 'react-markdown'; // Ensure user installs this or handle markdown manually?
// Actually, standard React doesn't render markdown. I should probably suggest installing react-markdown,
// or just render as text. The prompt says "answer in markdown".
// For now, I'll use simple text rendering or maybe a simple dangerousSetInnerHTML if the user trusts the backend.
// Wait, I can't install new npm packages easily without adding to package.json plan.
// I will render as whitespace-pre-wrap for now, which handles newlines.
// If I want bolding, I might need a parser.
// Let's stick to simple text for now to avoid dependency hell, but the prompt returns markdown.
// I'll assume simple text is fine or use a basic regex replacer for bolding if needed.
// Update: I'll use a simple formatter for **bold**.

const FormattedText = ({ text }) => {
    // Simple parser for bold text (**text**)
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return (
        <span>
            {parts.map((part, index) => {
                if (part.startsWith('**') && part.endsWith('**')) {
                    return <strong key={index}>{part.slice(2, -2)}</strong>;
                }
                return part;
            })}
        </span>
    );
};

const ChatInterface = ({ sessionId, initialCharts, initialMessages }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        // Load messages if provided, or empty
        if (initialMessages) {
            setMessages(initialMessages);
        } else {
            setMessages([]);
        }
    }, [sessionId, initialMessages]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const handleSendMessage = async (text) => {
        if (!text.trim()) return;

        const userMessage = { role: 'user', content: text };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await axios.post(`/api/chat/${sessionId}`, { prompt: text });
            const data = response.data;

            const botMessage = {
                role: 'assistant',
                content: data.answer,
                sources: data.sources,
                chart_data: data.charts
            };

            setMessages(prev => [...prev, botMessage]);
        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "Tyvärr uppstod ett fel. Försök igen."
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const QuickButton = ({ label, prompt, help }) => (
        <button
            onClick={() => handleSendMessage(prompt)}
            disabled={isLoading}
            className="flex-1 bg-white border border-gray-200 hover:bg-blue-50 hover:border-blue-200 text-gray-700 py-2 px-4 rounded-lg shadow-sm transition-all text-sm font-medium"
            title={help}
        >
            {label}
        </button>
    );

    return (
        <div className="flex flex-col h-full bg-gray-50">
            {/* Header / Charts Area - Only show if we have charts from initialization */}
            {initialCharts && initialCharts.length > 0 && messages.length === 0 && (
                <div className="p-6 bg-white border-b border-gray-200 flex-shrink-0">
                    <h3 className="text-lg font-semibold mb-4 text-gray-800">Finansiell Översikt</h3>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-x-auto">
                        {initialCharts.map((chart, idx) => (
                             <div key={idx} className="min-w-[300px]">
                                <ChartRenderer chartData={chart} />
                             </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
                {messages.length === 0 && !isLoading && (
                     <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 mt-10">
                        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4 text-blue-600">
                            <Bot size={32} />
                        </div>
                        <h3 className="text-xl font-semibold text-gray-800 mb-2">Välkommen!</h3>
                        <p className="max-w-md">Jag har analyserat dina dokument och är redo att svara på frågor.</p>
                     </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`flex max-w-3xl ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'} gap-3`}>

                            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-green-600 text-white'}`}>
                                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                            </div>

                            <div className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} min-w-0`}>
                                <div className={`p-4 rounded-2xl shadow-sm ${
                                    msg.role === 'user'
                                    ? 'bg-blue-600 text-white rounded-tr-none'
                                    : 'bg-white text-gray-800 rounded-tl-none border border-gray-100'
                                }`}>
                                    <div className="whitespace-pre-wrap leading-relaxed">
                                        <FormattedText text={msg.content} />
                                    </div>
                                </div>

                                {/* Render Charts if any */}
                                {msg.chart_data && msg.chart_data.length > 0 && (
                                    <div className="mt-4 w-full grid grid-cols-1 gap-4">
                                        {msg.chart_data.map((chart, cIdx) => (
                                            <ChartRenderer key={cIdx} chartData={chart} />
                                        ))}
                                    </div>
                                )}

                                {/* Render Sources if any */}
                                {msg.sources && msg.sources.length > 0 && (
                                    <div className="mt-2 w-full max-w-lg">
                                        <details className="group">
                                            <summary className="list-none cursor-pointer text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-colors">
                                                <div className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded hover:bg-gray-200">
                                                    <FileText size={12} />
                                                    <span>Visa källor ({msg.sources.length})</span>
                                                    <ChevronDown size={12} className="group-open:hidden" />
                                                    <ChevronUp size={12} className="hidden group-open:block" />
                                                </div>
                                            </summary>
                                            <div className="mt-2 text-sm text-gray-600 bg-gray-50 p-3 rounded border border-gray-200">
                                                {msg.sources.map((source, sIdx) => (
                                                    <div key={sIdx} className="mb-2 last:mb-0 border-b border-gray-200 last:border-0 pb-2 last:pb-0 whitespace-pre-wrap">
                                                        <FormattedText text={source} />
                                                    </div>
                                                ))}
                                            </div>
                                        </details>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="flex flex-row gap-3">
                            <div className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center">
                                <Bot size={16} />
                            </div>
                            <div className="bg-white p-4 rounded-2xl rounded-tl-none border border-gray-100 shadow-sm flex items-center gap-2">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-white border-t border-gray-200 flex-shrink-0">
                {messages.length === 0 && (
                     <div className="flex flex-wrap gap-3 mb-4 max-w-3xl mx-auto">
                        <QuickButton
                            label="Sammanfatta"
                            prompt="Sammanfatta de viktigaste finansiella punkterna i rapporten."
                            help="Sammanfatta de viktigaste finansiella punkterna i rapporten."
                        />
                        <QuickButton
                            label="Risker"
                            prompt="Vilka är de största riskerna som nämns?"
                            help="Vilka är de största riskerna som nämns?"
                        />
                        <QuickButton
                            label="Vinsttrend"
                            prompt="Hur ser vinstutvecklingen ut över tid?"
                            help="Hur ser vinstutvecklingen ut över tid?"
                        />
                     </div>
                )}

                <div className="max-w-4xl mx-auto relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendMessage(input)}
                        placeholder="Ställ en fråga om de finansiella rapporterna..."
                        disabled={isLoading}
                        className="w-full pl-4 pr-12 py-3 bg-gray-50 border border-gray-300 text-gray-900 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all shadow-sm"
                    />
                    <button
                        onClick={() => handleSendMessage(input)}
                        disabled={!input.trim() || isLoading}
                        className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 text-blue-600 hover:bg-blue-100 rounded-lg disabled:text-gray-400 disabled:hover:bg-transparent transition-colors"
                    >
                        <Send size={20} />
                    </button>
                </div>
                <div className="text-center mt-2 text-xs text-gray-400">
                    AI kan göra misstag. Kontrollera alltid viktiga uppgifter.
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;
