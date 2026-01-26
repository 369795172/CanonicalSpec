import React from 'react';
import { Target, Lightbulb, AlertCircle, Users, HelpCircle, History } from 'lucide-react';

const GenomeStatus = ({ genome, currentView, onViewChange }) => {
  if (!genome) return null;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Status Summary */}
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        gap: '8px', 
        padding: '12px', 
        background: 'rgba(255, 255, 255, 0.02)', 
        borderRadius: '8px' 
      }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '4px', fontWeight: 600 }}>
          状态摘要
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#888' }}>
            <Target size={14} /> 目标: {genome.goals?.length || 0}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#888' }}>
            <Lightbulb size={14} /> 假设: {genome.assumptions?.length || 0}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#888' }}>
            <AlertCircle size={14} /> 约束: {genome.constraints?.length || 0}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#888' }}>
            <Users size={14} /> 用户故事: {genome.user_stories?.length || 0}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--accent)' }}>
            <HelpCircle size={14} /> 待澄清: {genome.open_questions?.length || 0}
          </div>
        </div>
      </div>
      
      {/* History List */}
      <div style={{ padding: '12px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '8px', fontWeight: 600 }}>
          <History size={14} style={{ marginRight: '6px', display: 'inline', verticalAlign: 'middle' }} />
          演进历史
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
          <div 
            style={{ 
              padding: '8px 12px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              color: currentView === 'current' ? 'var(--accent)' : '#888',
              background: currentView === 'current' ? 'rgba(44, 107, 237, 0.2)' : 'transparent',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onClick={() => onViewChange('current')}
          >
            ● 当前 (第 {genome.round} 轮)
          </div>
          {(genome.history || []).slice().reverse().map((snapshot, idx) => (
            <div 
              key={snapshot.round}
              style={{ 
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                color: currentView === idx ? 'var(--accent)' : '#888',
                background: currentView === idx ? 'rgba(44, 107, 237, 0.2)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onClick={() => onViewChange(idx)}
            >
              ○ 第 {snapshot.round} 轮
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default GenomeStatus;
