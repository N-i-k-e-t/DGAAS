import { db } from '../db/database';

export interface WorkflowTrigger {
  workflow: string;
  payload?: any;
}

export const triggerWorkflow = async (workflow: string, payload: any = {}): Promise<{ success: boolean; message: string }> => {
  try {
    // Get connection settings from local DB/storage (defaulting to placeholders if not set)
    // In a real app, these would come from the Settings page inputs
    const baseUrl = localStorage.getItem('vaya_via_n8n_url') || 'https://n8n.vayavia.com';
    const authToken = localStorage.getItem('vaya_via_n8n_token') || '';

    const startTime = Date.now();
    
    const response = await fetch(`${baseUrl}/webhook/trigger-${workflow}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        ...payload,
        timestamp: new Date().toISOString(),
        source: 'VayaVia_Demand_Engine_UI'
      })
    });

    const duration = Date.now() - startTime;

    // Log the attempt to our local workflow_logs table
    await db.workflow_logs.add({
      workflow_name: workflow,
      status: response.ok ? 'success' : 'error',
      duration_ms: duration,
      started_at: new Date().toLocaleTimeString(),
      logs: response.ok ? 'Workflow triggered successfully' : `Failed to trigger: ${response.statusText}`
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return { 
      success: true, 
      message: `Workflow '${workflow}' triggered successfully.` 
    };
  } catch (error: any) {
    console.error('n8n Trigger Error:', error);
    
    // Fallback for local testing if no VPS is connected yet
    if (error.message.includes('Failed to fetch')) {
      return { 
        success: false, 
        message: 'Could not reach VPS. Please check n8n URL in Settings.' 
      };
    }

    return { 
      success: false, 
      message: error.message 
    };
  }
};
