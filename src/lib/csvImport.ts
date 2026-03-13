import Papa from 'papaparse';
import { db } from '../db/database';

export interface ImportResult {
  success: boolean;
  count: number;
  errors: string[];
}

export const importCsvToTable = async (tableName: string, file: File): Promise<ImportResult> => {
  return new Promise((resolve) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        const table = (db as any)[tableName];
        if (!table) {
          resolve({ success: false, count: 0, errors: [`Table ${tableName} not found in database`] });
          return;
        }

        try {
          // Clean data: remove 'id' if present to let Dexie generate it, and handle empty strings
          const cleanedData = results.data.map((row: any) => {
            const newRow = { ...row };
            if ('id' in newRow) delete newRow.id;
            // PDF specifically mentioned some numeric fields like monthly_traffic
            // We should ensure they are numbers if they look like it
            Object.keys(newRow).forEach(key => {
              if (newRow[key] === '') delete newRow[key];
            });
            return newRow;
          });

          await table.bulkAdd(cleanedData);
          resolve({ success: true, count: cleanedData.length, errors: [] });
        } catch (error: any) {
          resolve({ success: false, count: 0, errors: [error.message] });
        }
      },
      error: (error) => {
        resolve({ success: false, count: 0, errors: [error.message] });
      }
    });
  });
};

export const exportTableToCsv = async (tableName: string) => {
  const table = (db as any)[tableName];
  if (!table) return;

  const data = await table.toArray();
  const csv = Papa.unparse(data);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `${tableName}_export.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
