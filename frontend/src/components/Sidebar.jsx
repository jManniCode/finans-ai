import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { MessageSquare, Plus, Trash2, History } from 'lucide-react';

const Sidebar = ({ currentSessionId, onSelectSession, onNewAnalysis, onDeleteSession, refreshTrigger }) => {
    const [sessions, setSessions] = useState([]);

    useEffect(() => {
        fetchSessions();
    }, [currentSessionId, refreshTrigger]); // Refetch when session changes or triggered

    const fetchSessions = async () => {
        try {
            const response = await axios.get('/api/sessions');
            setSessions(response.data);
        } catch (err) {
            console.error("Failed to fetch sessions", err);
        }
    };

    return (
        <div className="w-64 bg-gray-900 text-white flex flex-col h-full border-r border-gray-800 flex-shrink-0">
            <div className="p-4 border-b border-gray-800">
                <h1 className="text-xl font-bold flex items-center gap-2">
                    <span>💰</span> Finans-AI
                </h1>
            </div>

            <div className="p-4">
                <button
                    onClick={onNewAnalysis}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors font-medium"
                >
                    <Plus size={18} />
                    Ny Analys
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 custom-scrollbar">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-2 mt-2">
                    Historik
                </div>
                <div className="space-y-1">
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                                currentSessionId === session.id
                                ? 'bg-gray-800 text-white'
                                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                            }`}
                            onClick={() => onSelectSession(session.id)}
                        >
                            <div className="flex items-center gap-3 overflow-hidden">
                                <MessageSquare size={16} className="flex-shrink-0" />
                                <span className="truncate text-sm">{session.title}</span>
                            </div>
                            {/* Always show delete button on hover, not just for active */}
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteSession(session.id);
                                }}
                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-400 rounded transition-all"
                                title="Ta bort"
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            <div className="p-4 border-t border-gray-800 text-xs text-gray-500 text-center">
                Finans-AI v2.0 (React)
            </div>
        </div>
    );
};

export default Sidebar;
