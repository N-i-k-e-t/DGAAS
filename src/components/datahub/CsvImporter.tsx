import React, { useState, useRef } from 'react';
import { Upload, X, CheckCircle2, AlertCircle, FileText, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { importCsvToTable } from '../../lib/csvImport';

interface CsvImporterProps {
  tableName: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CsvImporter: React.FC<CsvImporterProps> = ({ tableName, isOpen, onClose, onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; count: number; error?: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleImport = async () => {
    if (!file) return;
    setIsImporting(true);
    
    // Simulate interactive progress and wait to ensure Dexie is ready
    const res = await importCsvToTable(tableName, file);
    
    setTimeout(() => {
      setIsImporting(false);
      setResult({ success: res.success, count: res.count, error: res.errors[0] });
      if (res.success) {
        onSuccess();
      }
    }, 800);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 flex items-center justify-center z-[100] p-4">
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/80 backdrop-blur-md"
          />

          {/* Modal */}
          <motion.div 
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="relative w-full max-w-md bg-card border border-white/10 rounded-2xl shadow-2xl p-6 overflow-hidden"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center space-x-2">
                <Upload size={20} className="text-primary" />
                <span>Import Real Data</span>
              </h3>
              <button onClick={onClose} className="p-1 hover:bg-white/5 rounded-full text-text-secondary">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-6">
              <div className="bg-background rounded-lg border border-dashed border-white/10 p-8 text-center space-y-4">
                {file ? (
                  <div className="flex flex-col items-center">
                    <FileText size={48} className="text-primary mb-2" />
                    <div className="text-sm font-medium truncate max-w-xs">{file.name}</div>
                    <div className="text-[10px] text-text-secondary uppercase">{(file.size / 1024).toFixed(1)} KB</div>
                    <button 
                      onClick={() => setFile(null)}
                      className="mt-4 text-[10px] text-danger hover:underline font-bold"
                    >
                      REMOVE FILE
                    </button>
                  </div>
                ) : (
                  <div 
                    onClick={() => fileInputRef.current?.click()}
                    className="cursor-pointer group"
                  >
                    <div className="w-16 h-16 rounded-full bg-white/5 mx-auto flex items-center justify-center group-hover:bg-primary/10 transition-colors">
                      <Upload size={32} className="text-text-secondary group-hover:text-primary transition-colors" />
                    </div>
                    <div className="mt-4 text-sm text-text-secondary">
                      Click to upload CSV from Excel tab
                    </div>
                    <div className="text-[10px] text-text-secondary/50 mt-1 uppercase tracking-tighter">
                      Matches schema: {tableName}
                    </div>
                  </div>
                )}
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileChange} 
                  accept=".csv" 
                  className="hidden" 
                />
              </div>

              {result && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-4 rounded-xl border flex items-start space-x-3 ${
                    result.success ? 'bg-success/10 border-success/20 text-success' : 'bg-danger/10 border-danger/20 text-danger'
                  }`}
                >
                  {result.success ? <CheckCircle2 size={20} className="mt-0.5" /> : <AlertCircle size={20} className="mt-0.5" />}
                  <div>
                    <div className="text-sm font-bold">{result.success ? 'Import Complete' : 'Import Failed'}</div>
                    <div className="text-xs opacity-80">
                      {result.success ? `Successfully added ${result.count} real records to ${tableName.replace(/_/g, ' ')}.` : result.error}
                    </div>
                  </div>
                </motion.div>
              )}

              <div className="flex space-x-3 pt-2">
                <button 
                  onClick={onClose}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-white/5 text-sm font-medium hover:bg-white/5"
                >
                  Cancel
                </button>
                <button 
                  disabled={!file || isImporting}
                  onClick={handleImport}
                  className="flex-1 btn-primary py-2.5 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isImporting ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      <span>Importing...</span>
                    </>
                  ) : (
                    <span>Confirm Import</span>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
