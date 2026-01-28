import React from 'react';
import { RefreshCw, Plus, Check } from 'lucide-react';

const GenomeChanges = ({ changes }) => {
  if (!changes) return null;
  
  const hasChanges = 
    changes.new_assumptions?.length > 0 ||
    changes.new_constraints?.length > 0 ||
    changes.new_user_stories?.length > 0 ||
    changes.updated_fields?.length > 0 ||
    changes.decisions_made?.length > 0;
  
  if (!hasChanges) return null;
  
  return (
    <div style={{ 
      padding: '12px', 
      background: 'rgba(44, 107, 237, 0.05)', 
      borderRadius: '8px', 
      border: '1px solid rgba(44, 107, 237, 0.2)',
      marginBottom: '20px'
    }}>
      <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '8px', fontWeight: 600 }}>
        <RefreshCw size={14} style={{ marginRight: '6px', display: 'inline', verticalAlign: 'middle' }} />
        本轮更新
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
        {changes.new_assumptions?.map((a, i) => (
          <div key={`a-${i}`} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '0.8rem', 
            padding: '6px 8px', 
            borderRadius: '4px',
            background: 'rgba(16, 185, 129, 0.1)',
            color: '#10b981'
          }}>
            <Plus size={12} /> 假设: {a}
          </div>
        ))}
        {changes.new_constraints?.map((c, i) => (
          <div key={`c-${i}`} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '0.8rem', 
            padding: '6px 8px', 
            borderRadius: '4px',
            background: 'rgba(16, 185, 129, 0.1)',
            color: '#10b981'
          }}>
            <Plus size={12} /> 约束: {c}
          </div>
        ))}
        {changes.new_user_stories?.map((us, i) => (
          <div key={`us-${i}`} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '0.8rem', 
            padding: '6px 8px', 
            borderRadius: '4px',
            background: 'rgba(16, 185, 129, 0.1)',
            color: '#10b981'
          }}>
            <Plus size={12} /> 用户故事: {us}
          </div>
        ))}
        {changes.updated_fields?.map((field, i) => (
          <div key={`field-${i}`} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '0.8rem', 
            padding: '6px 8px', 
            borderRadius: '4px',
            background: 'rgba(59, 130, 246, 0.1)',
            color: '#3b82f6'
          }}>
            <RefreshCw size={12} /> {field}
          </div>
        ))}
        {changes.decisions_made?.map((d, i) => (
          <div key={`d-${i}`} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '0.8rem', 
            padding: '6px 8px', 
            borderRadius: '4px',
            background: 'rgba(44, 107, 237, 0.1)',
            color: 'var(--accent)'
          }}>
            <Check size={12} /> 决策: {d}
          </div>
        ))}
      </div>
    </div>
  );
};

export default GenomeChanges;
