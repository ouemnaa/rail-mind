/**
 * Conflict Workflow Management Hook
 * =================================
 * 
 * Manages the complete lifecycle of conflicts:
 * 1. Detect and save active conflicts
 * 2. Track resolution attempts
 * 3. Archive resolved conflicts with outcomes
 * 4. Retrieve and analyze archived conflicts
 */

import { useState, useCallback, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8002';

export interface ArchivedConflict {
  conflict_id: string;
  conflict_type: string;
  location: string;
  involved_trains: string[];
  detected_at: string;
  resolution_applied_at: string;
  resolution_id: string;
  resolution_strategy: string;
  success_metrics: {
    delay_reduction_percent: number;
    efficiency_gain_percent: number;
    confidence_score: number;
  };
  kpi_improvement: {
    original_total_delay_sec: number;
    resolved_total_delay_sec: number;
    original_on_time_count: number;
    resolved_on_time_count: number;
  };
  is_archived: boolean;
  archived_at: string;
}

export interface ConflictWorkflowState {
  active_conflicts: string[]; // IDs of detected but unresolved conflicts
  resolved_conflicts: string[]; // IDs of resolved conflicts
  archived_conflicts: ArchivedConflict[]; // Full archived conflict data
  in_progress: boolean;
  last_archive_time: string | null;
  total_resolved: number;
  total_archived: number;
}

interface UseConflictWorkflowReturn {
  workflow: ConflictWorkflowState;
  
  // Conflict Detection & Saving
  saveDetectedConflict: (conflict: any) => Promise<{ success: boolean; filename: string }>;
  removeFromActive: (conflictId: string) => void;
  
  // Resolution Tracking
  markResolved: (conflictId: string, resolutionId: string, strategy: string) => void;
  
  // Archival & Retrieval
  archiveResolvedConflict: (
    conflictId: string,
    resolutionId: string,
    strategy: string,
    comparisonResults: any,
    finalKpis: any
  ) => Promise<{ success: boolean; message: string }>;
  
  getArchivedConflicts: () => Promise<ArchivedConflict[]>;
  getConflictStats: () => Promise<any>;
  
  // State Management
  clearWorkflow: () => void;
}

/**
 * Hook for managing the complete conflict workflow
 */
export function useConflictWorkflow(): UseConflictWorkflowReturn {
  const [workflow, setWorkflow] = useState<ConflictWorkflowState>({
    active_conflicts: [],
    resolved_conflicts: [],
    archived_conflicts: [],
    in_progress: false,
    last_archive_time: null,
    total_resolved: 0,
    total_archived: 0,
  });

  /**
   * Step 1: Save detected conflict to backend
   */
  const saveDetectedConflict = useCallback(async (conflict: any) => {
    try {
      setWorkflow(prev => ({ ...prev, in_progress: true }));

      // Call backend to save current state with conflict
      const response = await fetch(`${API_BASE_URL}/api/conflicts/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conflict_id: conflict.conflict_id,
          timestamp: new Date().toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to save conflict: ${response.status}`);
      }

      const data = await response.json();

      // Add to active conflicts
      setWorkflow(prev => ({
        ...prev,
        active_conflicts: [...new Set([...prev.active_conflicts, conflict.conflict_id])],
      }));

      console.log('✅ Conflict saved:', data.filename);
      return {
        success: true,
        filename: data.filename,
      };
    } catch (error) {
      console.error('❌ Failed to save conflict:', error);
      return {
        success: false,
        filename: '',
      };
    }
  }, []);

  /**
   * Step 2: Remove conflict from active state
   */
  const removeFromActive = useCallback((conflictId: string) => {
    setWorkflow(prev => ({
      ...prev,
      active_conflicts: prev.active_conflicts.filter(id => id !== conflictId),
    }));
    console.log(`✅ Conflict ${conflictId} removed from active state`);
  }, []);

  /**
   * Step 3: Mark conflict as resolved
   */
  const markResolved = useCallback((conflictId: string, resolutionId: string, strategy: string) => {
    setWorkflow(prev => ({
      ...prev,
      resolved_conflicts: [...new Set([...prev.resolved_conflicts, conflictId])],
      active_conflicts: prev.active_conflicts.filter(id => id !== conflictId),
      total_resolved: prev.total_resolved + 1,
    }));
    console.log(`✅ Conflict ${conflictId} marked as resolved with ${resolutionId}`);
  }, []);

  /**
   * Step 4: Archive resolved conflict with full outcome data to Qdrant
   */
  const archiveResolvedConflict = useCallback(
    async (
      conflictId: string,
      resolutionId: string,
      strategy: string,
      comparisonResults: any,
      finalKpis: any
    ) => {
      try {
        setWorkflow(prev => ({ ...prev, in_progress: true }));

        // Prepare archive request
        const archiveData = {
          conflict_id: conflictId,
          resolution_id: resolutionId,
          resolution_strategy: strategy,
          comparison_results: comparisonResults,
          final_kpis: finalKpis,
          timestamp: new Date().toISOString(),
        };

        // Send to backend archival endpoint
        const response = await fetch(`${API_BASE_URL}/api/conflicts/archive`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(archiveData),
        });

        if (!response.ok) {
          throw new Error(`Archive failed: ${response.status}`);
        }

        const result = await response.json();

        // Update workflow state
        setWorkflow(prev => ({
          ...prev,
          in_progress: false,
          last_archive_time: new Date().toISOString(),
          total_archived: prev.total_archived + 1,
          resolved_conflicts: prev.resolved_conflicts.filter(id => id !== conflictId),
        }));

        console.log('✅ Conflict archived to Qdrant:', result.message);
        return {
          success: true,
          message: result.message,
        };
      } catch (error) {
        console.error('❌ Failed to archive conflict:', error);
        setWorkflow(prev => ({ ...prev, in_progress: false }));
        return {
          success: false,
          message: `Archive failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        };
      }
    },
    []
  );

  /**
   * Retrieve all archived conflicts
   */
  const getArchivedConflicts = useCallback(async (): Promise<ArchivedConflict[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conflicts/archived`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch archived conflicts: ${response.status}`);
      }

      const data = await response.json();
      return data.conflicts || [];
    } catch (error) {
      console.error('❌ Failed to retrieve archived conflicts:', error);
      return [];
    }
  }, []);

  /**
   * Get workflow statistics
   */
  const getConflictStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conflicts/stats`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch stats: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('❌ Failed to retrieve conflict stats:', error);
      return {
        total_detected: 0,
        total_resolved: workflow.total_resolved,
        total_archived: workflow.total_archived,
        resolution_success_rate: 0,
        avg_resolution_time_sec: 0,
      };
    }
  }, [workflow.total_resolved, workflow.total_archived]);

  /**
   * Clear all workflow state
   */
  const clearWorkflow = useCallback(() => {
    setWorkflow({
      active_conflicts: [],
      resolved_conflicts: [],
      archived_conflicts: [],
      in_progress: false,
      last_archive_time: null,
      total_resolved: 0,
      total_archived: 0,
    });
    console.log('🔄 Workflow state cleared');
  }, []);

  /**
   * Load archived conflicts on mount
   */
  useEffect(() => {
    getArchivedConflicts().then(conflicts => {
      setWorkflow(prev => ({
        ...prev,
        archived_conflicts: conflicts,
        total_archived: conflicts.length,
      }));
    });
  }, [getArchivedConflicts]);

  return {
    workflow,
    saveDetectedConflict,
    removeFromActive,
    markResolved,
    archiveResolvedConflict,
    getArchivedConflicts,
    getConflictStats,
    clearWorkflow,
  };
}
