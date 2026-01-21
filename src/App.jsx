import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  RotateCcw,
  ChevronRight,
  Mic,
  FileText,
  CheckCircle2,
  Trash2,
  HelpCircle,
  User,
  Download,
  History,
  Lightbulb,
  Github,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const App = () => {
  const [features, setFeatures] = useState(() => {
    const saved = localStorage.getItem('canonical_features');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentFeature, setCurrentFeature] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newFeatureInput, setNewFeatureInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('list'); // 'list', 'create', 'view'

  // Fetch features list
  useEffect(() => {
    fetchFeatures();
  }, []);

  const fetchFeatures = async () => {
    try {
      const res = await fetch('/api/v1/features', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setFeatures(data.features || []);
        localStorage.setItem('canonical_features', JSON.stringify(data.features || []));
      }
    } catch (err) {
      console.error('Failed to fetch features:', err);
    }
  };

  const handleCreateFeature = async () => {
    if (!newFeatureInput.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: newFeatureInput,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.feature_id) {
          await fetchFeatures();
          setCurrentFeature(data.feature_id);
          setActiveTab('view');
          setShowCreateModal(false);
          setNewFeatureInput('');
        }
      }
    } catch (err) {
      console.error('Failed to create feature:', err);
      alert('创建功能失败，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  };

  const currentDisplayData = activeTab === 'view' && currentFeature
    ? features.find(f => f.feature_id === currentFeature)
    : null;

  return (
    <div className="app-container">
      <header>
        <div className="logo">
          Canonical Spec <span>Manager</span>
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <button
            className="btn-create"
            onClick={() => setShowCreateModal(true)}
          >
            <Sparkles size={16} style={{ marginRight: '8px' }} />
            创建功能
          </button>
          <a
            href="https://github.com/369795172/CanonicalSpec"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-github"
            title="View on GitHub"
          >
            <Github size={18} />
          </a>
        </div>
      </header>
      <div className="main-content">
        <div className="sidebar">
          <div className={`sidebar-item ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            <FileText size={16} /> 功能列表
          </div>
          <div className={`sidebar-item ${activeTab === 'create' ? 'active' : ''}`}
            onClick={() => setShowCreateModal(true)}
          >
            <Sparkles size={16} /> 创建功能
          </div>
          <a
            href="https://github.com/369795172/CanonicalSpec/blob/main/docs/canonical_spec.md"
            target="_blank"
            rel="noopener noreferrer"
            className="sidebar-item"
          >
            <Lightbulb size={16} /> 使用文档
          </a>
        </div>
        <div className="content-pane">
          {activeTab === 'list' && (
            <div className="features-list">
              {features.length === 0 ? (
                <div className="empty-state">
                  <FileText size={48} style={{ marginBottom: '20px', opacity: 0.3 }} />
                  <h2>暂无功能</h2>
                  <p>点击"创建功能"开始创建新的 Canonical Spec。</p>
                </div>
              ) : (
                features.map((feature, index) => {
                  const statusColors = {
                    draft: '#888',
                    clarifying: '#f59e0b',
                    executable_ready: '#10b981',
                    published: '#059669',
                    hold: '#f59e0b',
                    drop: '#ef4444',
                  };
                  return (
                    <div
                      key={feature.feature_id}
                      className={`feature-card ${activeTab === 'view' && currentFeature === feature.feature_id ? 'selected' : ''}`}
                      onClick={() => {
                        setCurrentFeature(feature.feature_id);
                        setActiveTab('view');
                      }}
                    >
                      <div className="feature-header">
                        <span className="feature-id">{feature.feature_id}</span>
                        <span
                          className="status-badge"
                          style={{ backgroundColor: statusColors[feature.status] }}
                        >
                          {feature.status}
                        </span>
                      </div>
                      <h3 className="feature-title">
                        {feature.title || feature.feature_input?.substring(0, 50) + '...'}
                      </h3>
                      <p className="feature-description">
                        {feature.spec?.feature?.goal || '点击查看详情'}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {activeTab === 'view' && currentDisplayData && (
            <FeatureDetailView featureId={currentFeature} onBack={() => setActiveTab('list')} />
          )}

          {activeTab === 'create' && (
            <CreateModal
              isOpen={showCreateModal}
              onClose={() => {
                setShowCreateModal(false);
                setNewFeatureInput('');
              }}
              onSubmit={handleCreateFeature}
              loading={loading}
            />
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </div>
  );
};

// Feature Detail View Component
const FeatureDetailView = ({ featureId, onBack }) => {
  const [featureData, setFeatureData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFeatureDetails();
  }, [featureId]);

  const fetchFeatureDetails = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/features/${featureId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setFeatureData(data);
      }
    } catch (err) {
      console.error('Failed to fetch feature details:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loader"></div>
        <span>加载中...</span>
      </div>
    );
  }

  if (!featureData) {
    return null;
  }

  const statusColors = {
    draft: '#888',
    clarifying: '#f59e0b',
    executable_ready: '#10b981',
    published: '#059669',
    hold: '#f59e0b',
    drop: '#ef4444',
  };

  const { spec, feature } = featureData;

  return (
    <div className="feature-detail-view">
      <div className="detail-header">
        <button className="btn-back" onClick={onBack}>
          <ChevronRight size={20} style={{ transform: 'rotate(180deg)' }} />
          返回
        </button>
        <div className="feature-title-section">
          <h1>{feature.title || feature.feature_input}</h1>
          <span className="status-badge" style={{ backgroundColor: statusColors[feature.status] }}>
            {feature.status}
          </span>
        </div>
      </div>

      <div className="detail-content">
        {spec && (
          <>
            {/* Spec Header */}
            <div className="spec-section">
              <h3 className="section-heading">目标与非目标</h3>
              <div className="spec-content">
                <div className="spec-item">
                  <strong>目标：</strong>
                  <p>{spec.feature?.goal}</p>
                </div>
                {spec.feature?.non_goals && spec.feature.non_goals.length > 0 && (
                  <div className="spec-item">
                    <strong>非目标：</strong>
                    <ul>
                      {spec.feature.non_goals.map((goal, i) => (
                        <li key={i}>{goal}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Planning */}
            {spec.planning && (
              <div className="spec-section">
                <h3 className="section-heading">已知假设与约束</h3>
                <div className="spec-content">
                  {spec.planning.known_assumptions && spec.planning.known_assumptions.length > 0 && (
                    <div className="spec-item">
                      <strong>已知假设：</strong>
                      <ul>
                        {spec.planning.known_assumptions.map((assumption, i) => (
                          <li key={i}>{assumption}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {spec.planning.constraints && spec.planning.constraints.length > 0 && (
                    <div className="spec-item">
                      <strong>约束条件：</strong>
                      <ul>
                        {spec.planning.constraints.map((constraint, i) => (
                          <li key={i}>{constraint}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tasks */}
            {spec.tasks && spec.tasks.length > 0 && (
              <div className="spec-section">
                <h3 className="section-heading">任务列表</h3>
                <div className="tasks-list">
                  {spec.tasks.map((task, i) => (
                    <div key={i} className="task-card">
                      <span className="task-id">{task.id}</span>
                      <h4>{task.title}</h4>
                      <p>{task.description}</p>
                      {task.dependencies && task.dependencies.length > 0 && (
                        <div className="task-dependencies">
                          <strong>依赖：</strong>
                          {task.dependencies.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* VV Items */}
            {spec.vv && spec.vv.length > 0 && (
              <div className="spec-section">
                <h3 className="section-heading">验证与验证 (V&V)</h3>
                <div className="vv-list">
                  {spec.vv.map((vv, i) => (
                    <div key={i} className="vv-card">
                      <h4>{vv.title}</h4>
                      <ReactMarkdown>{vv.description}</ReactMarkdown>
                      {vv.evidence_required && vv.evidence_required.length > 0 && (
                        <div className="vv-evidence">
                          <strong>所需证据：</strong>
                          <ul>
                            {vv.evidence_required.map((evidence, j) => (
                              <li key={j}>{evidence}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Project Context */}
            {spec.project_context_ref && (
              <div className="spec-section">
                <h3 className="section-heading">项目上下文</h3>
                <div className="spec-content">
                  <p><strong>项目 ID：</strong>{spec.project_context_ref.project_record_id}</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// Create Modal Component
const CreateModal = ({ isOpen, onClose, onSubmit, loading }) => {
  const [input, setInput] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(input);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>创建新功能</h2>
          <button className="btn-close" onClick={onClose}>
            <Trash2 size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>
              <FileText size={16} style={{ marginRight: '8px' }} />
              功能描述
            </label>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="描述你想实现的功能，例如：添加用户登录功能，支持用户名密码登录和手机验证码登录"
              rows={6}
              disabled={loading}
            />
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
              {loading ? '创建中...' : '开始分析'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default App;
