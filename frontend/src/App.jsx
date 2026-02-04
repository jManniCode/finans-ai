import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import FileUpload from './components/FileUpload';
import ChatInterface from './components/ChatInterface';

function App() {
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [sessionData, setSessionData] = useState(null);
    const [isLoadingSession, setIsLoadingSession] = useState(false);
    const [refreshSidebar, setRefreshSidebar] = useState(0);

    const handleNewAnalysis = () => {
        setCurrentSessionId(null);
        setSessionData(null);
    };

    const handleSelectSession = async (sessionId) => {
        if (sessionId === currentSessionId) return;

        setIsLoadingSession(true);
        try {
            const response = await axios.get(`/api/sessions/${sessionId}`);
            setSessionData(response.data);
            setCurrentSessionId(sessionId);
        } catch (err) {
            console.error("Failed to load session", err);
        } finally {
            setIsLoadingSession(false);
        }
    };

    const handleUploadSuccess = (data) => {
        // data contains session_id and initial_charts
        // We need to construct sessionData format roughly matching what GET /sessions/{id} returns
        setCurrentSessionId(data.session_id);
        setSessionData({
            id: data.session_id,
            messages: [],
            initial_charts: data.initial_charts
        });
        setRefreshSidebar(prev => prev + 1); // Refresh sidebar to show new session
    };

    const handleDeleteSession = async (sessionId) => {
         if (window.confirm("Är du säker på att du vill ta bort denna analys?")) {
             try {
                 await axios.delete(`/api/sessions/${sessionId}`);
                 setRefreshSidebar(prev => prev + 1);
                 if (currentSessionId === sessionId) {
                     handleNewAnalysis();
                 }
             } catch (err) {
                 console.error(err);
             }
         }
    };

    return (
        <div className="flex h-screen w-screen overflow-hidden bg-gray-100 font-sans text-gray-900">
            <Sidebar
                currentSessionId={currentSessionId}
                onSelectSession={handleSelectSession}
                onNewAnalysis={handleNewAnalysis}
                onDeleteSession={handleDeleteSession}
                refreshTrigger={refreshSidebar}
            />

            <main className="flex-1 h-full relative flex flex-col min-w-0">
                {isLoadingSession ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                    </div>
                ) : !currentSessionId ? (
                    <FileUpload onUploadSuccess={handleUploadSuccess} />
                ) : (
                    <ChatInterface
                        key={currentSessionId} // Force remount on session change
                        sessionId={currentSessionId}
                        initialCharts={sessionData?.initial_charts}
                        initialMessages={sessionData?.messages}
                    />
                )}
            </main>
        </div>
    );
}

export default App;
