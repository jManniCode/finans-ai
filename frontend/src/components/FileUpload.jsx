import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, Loader2, AlertCircle } from 'lucide-react';

const FileUpload = ({ onUploadSuccess }) => {
    const [files, setFiles] = useState([]);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState(null);

    const handleFileChange = (e) => {
        setFiles(Array.from(e.target.files));
        setError(null);
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setIsUploading(true);
        setError(null);

        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        try {
            const response = await axios.post('/api/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            onUploadSuccess(response.data);
        } catch (err) {
            console.error(err);
            setError(err.response?.data?.detail || "Upload failed");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto p-6">
            <div className="w-full bg-white rounded-xl shadow-lg p-8">
                <div className="text-center mb-8">
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">Starta Ny Analys</h2>
                    <p className="text-gray-500">Ladda upp dina finansiella rapporter (PDF) för att komma igång.</p>
                </div>

                <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 mb-6 flex flex-col items-center justify-center bg-gray-50 hover:bg-gray-100 transition-colors">
                    <input
                        type="file"
                        multiple
                        accept=".pdf"
                        onChange={handleFileChange}
                        className="hidden"
                        id="file-upload"
                    />
                    <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                        <Upload className="w-12 h-12 text-blue-500 mb-4" />
                        <span className="text-gray-700 font-medium">Klicka för att välja filer</span>
                        <span className="text-gray-400 text-sm mt-1">Endast PDF-filer</span>
                    </label>
                </div>

                {files.length > 0 && (
                    <div className="mb-6 space-y-2">
                        {files.map((file, index) => (
                            <div key={index} className="flex items-center text-sm text-gray-700 bg-gray-50 p-2 rounded">
                                <FileText className="w-4 h-4 mr-2 text-gray-500" />
                                {file.name}
                            </div>
                        ))}
                    </div>
                )}

                {error && (
                    <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg flex items-center">
                        <AlertCircle className="w-5 h-5 mr-2" />
                        {error}
                    </div>
                )}

                <button
                    onClick={handleUpload}
                    disabled={!files.length || isUploading}
                    className={`w-full py-3 rounded-lg font-semibold text-white flex items-center justify-center transition-all ${
                        !files.length || isUploading
                        ? 'bg-gray-300 cursor-not-allowed'
                        : 'bg-blue-600 hover:bg-blue-700 shadow-md hover:shadow-lg'
                    }`}
                >
                    {isUploading ? (
                        <>
                            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                            Processar...
                        </>
                    ) : (
                        "Processera & Analysera"
                    )}
                </button>
            </div>
        </div>
    );
};

export default FileUpload;
