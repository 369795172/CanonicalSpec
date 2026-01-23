import React, { useState, useEffect, useRef } from 'react';
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
  Square,
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
  
  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [audioLevels, setAudioLevels] = useState([]);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);
  const audioChunksRef = useRef([]);

  // Fetch features list
  useEffect(() => {
    fetchFeatures();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
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

  // Audio recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Set up audio context for visualization
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const microphone = audioContext.createMediaStreamSource(stream);
      
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      microphone.connect(analyser);
      
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      
      // Set up MediaRecorder
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(audioBlob);
        stream.getTracks().forEach(track => track.stop());
        if (audioContextRef.current) {
          audioContextRef.current.close();
        }
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      setAudioLevels([]);
      
      // Start visualization
      visualizeAudio();
    } catch (err) {
      console.error("Error starting recording:", err);
      alert("Failed to start recording. Please check microphone permissions.");
    }
  };
  
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    }
  };
  
  const visualizeAudio = () => {
    if (!analyserRef.current) return;
    
    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    let lastSampleTime = Date.now();
    const sampleInterval = 100; // Sample every 100ms (10fps for 10 seconds = 100 samples)
    
    const updateVisualization = () => {
      if (!analyserRef.current) return;
      
      const now = Date.now();
      
      // Only sample at 10fps (every 100ms) to get 10 seconds of data
      if (now - lastSampleTime >= sampleInterval) {
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate average volume
        const sum = dataArray.reduce((a, b) => a + b, 0);
        const average = sum / bufferLength;
        const normalizedLevel = Math.min(average / 128, 1); // Normalize to 0-1
        
        setAudioLevels(prev => {
          const newLevels = [...prev, normalizedLevel];
          // Keep only last 10 seconds (10fps * 10 seconds = 100 samples)
          const maxSamples = 100;
          return newLevels.slice(-maxSamples);
        });
        
        lastSampleTime = now;
      }
      
      // Continue animation if still recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        animationFrameRef.current = requestAnimationFrame(updateVisualization);
      }
    };
    
    updateVisualization();
  };
  
  const transcribeAudio = async (audioBlob) => {
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.webm');
      
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error('Transcription failed');
      }
      
      const result = await response.json();
      if (result.text) {
        setNewFeatureInput(prev => prev + (prev ? ' ' : '') + result.text);
      }
    } catch (err) {
      console.error("Transcription error:", err);
      alert("Failed to transcribe audio. Please try again.");
    } finally {
      setIsTranscribing(false);
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
        <div className="discovery-pane">
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
                        {feature.title || '未命名功能'}
                      </h3>
                      <p className="feature-description">
                        {feature.spec?.feature?.goal || '点击查看详情'}
                      </p>
                      {feature.status === 'clarifying' && (
                        <div className="clarifying-indicator">
                          <HelpCircle size={14} />
                          <span>需要补充信息</span>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {activeTab === 'view' && currentDisplayData && (
            <FeatureDetailView featureId={currentFeature} onBack={() => setActiveTab('list')} />
          )}
        </div>

        <div className="sidebar">
          <div className="sidebar-item">
            <div className="section-title">
              <FileText size={16} /> 功能列表
            </div>
            <div className="history-list">
              <div
                className={`history-item ${activeTab === 'list' ? 'active' : ''}`}
                onClick={() => setActiveTab('list')}
              >
                所有功能 ({features.length})
              </div>
            </div>
          </div>

          <div className="sidebar-item">
            <div className="section-title">
              <Lightbulb size={16} /> 快速操作
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                className={activeTab === 'create' ? 'active' : ''}
                onClick={() => setShowCreateModal(true)}
                style={{ width: '100%', justifyContent: 'flex-start' }}
              >
                <Sparkles size={16} /> 创建功能
              </button>
              <a
                href="https://github.com/369795172/CanonicalSpec/blob/main/docs/canonical_spec.md"
                target="_blank"
                rel="noopener noreferrer"
                className="sidebar-item"
                style={{ marginBottom: 0 }}
              >
                <Lightbulb size={16} /> 使用文档
              </a>
            </div>
          </div>

          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-dim)', fontSize: '0.8rem', padding: '15px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid var(--border)' }}>
            <Lightbulb size={16} />
            提示：请详细描述功能需求、用户角色和使用场景。
          </div>
        </div>
      </div>

      <div className="controls">
        <div className="input-wrapper">
          {isRecording && (
            <div className="waveform-container">
              <div className="waveform">
                {audioLevels.map((level, i) => (
                  <div
                    key={i}
                    className="waveform-bar"
                    style={{
                      height: `${Math.max(level * 100, 5)}%`,
                      backgroundColor: `rgba(44, 107, 237, ${0.3 + level * 0.7})`
                    }}
                  />
                ))}
              </div>
            </div>
          )}
          <textarea
            placeholder="描述你想实现的功能，或点击麦克风按钮进行语音输入..."
            value={newFeatureInput}
            onChange={(e) => setNewFeatureInput(e.target.value)}
            disabled={loading || isRecording}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !loading && !isRecording) {
                e.preventDefault();
                handleCreateFeature();
              }
            }}
          />
          <div style={{ position: 'static', right: '20px', bottom: '20px', display: 'flex', gap: '10px', alignItems: 'center', justifyContent: 'center' }}>
            {isTranscribing && (
              <div className="transcribing-indicator">
                <div className="loader" style={{ width: 16, height: 16, borderWidth: 2 }}></div>
                <span style={{ fontSize: '0.75rem', color: 'var(--accent)', marginLeft: '8px' }}>Transcribing...</span>
              </div>
            )}
            <button
              className={`btn-voice ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading || isTranscribing}
              title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Start voice input"}
            >
              {isRecording ? <Square size={24} /> : isTranscribing ? <div className="loader" style={{ width: 20, height: 20, borderWidth: 2 }} /> : <Mic size={20} />}
            </button>
          </div>
        </div>
        <button
          className="btn-generate"
          onClick={handleCreateFeature}
          disabled={loading || isRecording || !newFeatureInput.trim()}
        >
          {loading ? <div className="loader" style={{ width: 24, height: 24, borderWidth: 2 }} /> : <Sparkles size={32} />}
        </button>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateModal
          isOpen={showCreateModal}
          onClose={() => {
            setShowCreateModal(false);
            setNewFeatureInput('');
          }}
          input={newFeatureInput}
          setInput={setNewFeatureInput}
          onSubmit={handleCreateFeature}
          loading={loading}
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          audioLevels={audioLevels}
          startRecording={startRecording}
          stopRecording={stopRecording}
        />
      )}

      {loading && (
        <div className="status-overlay">
          <div className="loader"></div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--accent)', letterSpacing: '1px', textTransform: 'uppercase', fontWeight: 700 }}>
              AI分析中...
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>正在分析需求并生成规格...</span>
          </div>
        </div>
      )}
    </div>
  );
};

// Clarification Panel Component
const ClarificationPanel = ({ questions, answers, setAnswers, onSubmit, isSubmitting }) => {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="clarification-panel">
      <div className="clarification-header">
        <HelpCircle size={18} />
        <span>需要补充的信息 ({questions.length})</span>
      </div>
      {questions.map((q, i) => (
        <div key={q.id || i} className="question-item">
          <label>{q.question}</label>
          <span className="field-hint">字段: {q.field_path}</span>
          <textarea
            value={answers[q.field_path] || ''}
            onChange={(e) => setAnswers({...answers, [q.field_path]: e.target.value})}
            placeholder="请输入..."
            rows={3}
          />
        </div>
      ))}
      <button 
        onClick={onSubmit} 
        disabled={isSubmitting || Object.keys(answers).length === 0}
        className="btn-primary"
        style={{ marginTop: '16px', width: '100%' }}
      >
        {isSubmitting ? '提交中...' : '提交答案'}
      </button>
    </div>
  );
};

// Feature Detail View Component
const FeatureDetailView = ({ featureId, onBack }) => {
  const [featureData, setFeatureData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clarifyQuestions, setClarifyQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchFeatureDetails();
  }, [featureId]);

  useEffect(() => {
    if (featureData?.gate_result?.clarify_questions) {
      setClarifyQuestions(featureData.gate_result.clarify_questions);
    } else {
      setClarifyQuestions([]);
    }
    setAnswers({});
  }, [featureData]);

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

  const handleSubmitAnswers = async () => {
    setIsSubmitting(true);
    try {
      const res = await fetch(`/api/v1/features/${featureId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      if (res.ok) {
        const data = await res.json();
        setFeatureData(data);
        setAnswers({});
      } else {
        const error = await res.json();
        alert(`提交失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      console.error('Failed to submit answers:', err);
      alert('提交答案失败，请重试');
    } finally {
      setIsSubmitting(false);
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
          <h1>{feature.title || '未命名功能'}</h1>
          <span className="status-badge" style={{ backgroundColor: statusColors[feature.status] }}>
            {feature.status}
          </span>
        </div>
      </div>

      <div className="detail-content">
        {/* Clarification Panel */}
        {feature.status === 'clarifying' && clarifyQuestions.length > 0 && (
          <ClarificationPanel
            questions={clarifyQuestions}
            answers={answers}
            setAnswers={setAnswers}
            onSubmit={handleSubmitAnswers}
            isSubmitting={isSubmitting}
          />
        )}

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

// Create Modal Component with Refinement Support
const CreateModal = ({ isOpen, onClose, input, setInput, onSubmit, loading, isRecording, isTranscribing, audioLevels, startRecording, stopRecording }) => {
  const [refineResult, setRefineResult] = useState(null);
  const [refineContext, setRefineContext] = useState({
    conversation_history: [],
    round: 0,
    feature_id: null,
    additional_context: {}
  });
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineAnswers, setRefineAnswers] = useState({});

  if (!isOpen) return null;

  const handleRefine = async () => {
    if (!input.trim()) return;
    setRefineLoading(true);
    try {
      const res = await fetch('/api/v1/refine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: input,
          context: refineContext
        })
      });
      if (res.ok) {
        const data = await res.json();
        setRefineResult(data);
        // Update context with new conversation history
        setRefineContext(prev => ({
          ...prev,
          conversation_history: [
            ...prev.conversation_history,
            { role: 'user', content: input },
            { role: 'assistant', content: JSON.stringify(data) }
          ],
          round: data.round || prev.round + 1
        }));
      } else {
        const error = await res.json();
        alert(`需求分析失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      console.error('Failed to refine requirement:', err);
      alert('需求分析失败，请重试');
    } finally {
      setRefineLoading(false);
    }
  };

  const handleRefineFeedback = async (feedback) => {
    setRefineLoading(true);
    try {
      const res = await fetch('/api/v1/refine/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: feedback,
          context: refineContext
        })
      });
      if (res.ok) {
        const data = await res.json();
        setRefineResult(data);
        setRefineContext(prev => ({
          ...prev,
          conversation_history: [
            ...prev.conversation_history,
            { role: 'user', content: feedback },
            { role: 'assistant', content: JSON.stringify(data) }
          ],
          round: data.round || prev.round + 1
        }));
      } else {
        const error = await res.json();
        alert(`反馈处理失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      console.error('Failed to apply feedback:', err);
      alert('反馈处理失败，请重试');
    } finally {
      setRefineLoading(false);
    }
  };

  const handleSubmitRefined = async () => {
    if (!refineResult || !refineResult.ready_to_compile) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: input,
          refine_result: refineResult
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.feature_id) {
          onSubmit(); // This will trigger parent's onSubmit which handles navigation
        }
      }
    } catch (err) {
      console.error('Failed to create feature:', err);
      alert('创建功能失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (refineResult && refineResult.ready_to_compile) {
      handleSubmitRefined();
    } else {
      handleRefine();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', maxHeight: '90vh', overflowY: 'auto' }}>
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
            <div style={{ position: 'relative' }}>
              {isRecording && (
                <div className="waveform-container" style={{ position: 'absolute', left: '12px', bottom: '12px', width: '200px', height: '50px' }}>
                  <div className="waveform">
                    {audioLevels.map((level, i) => (
                      <div
                        key={i}
                        className="waveform-bar"
                        style={{
                          height: `${Math.max(level * 100, 5)}%`,
                          backgroundColor: `rgba(44, 107, 237, ${0.3 + level * 0.7})`
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="描述你想实现的功能，例如：我想做一个健身网站"
                rows={6}
                disabled={loading || isRecording || refineLoading}
                style={{ paddingLeft: isRecording ? '240px' : '12px', paddingRight: '80px' }}
              />
              <div style={{ position: 'absolute', right: '12px', bottom: '12px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                {isTranscribing && (
                  <div className="transcribing-indicator" style={{ position: 'static' }}>
                    <div className="loader" style={{ width: 16, height: 16, borderWidth: 2 }}></div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--accent)', marginLeft: '8px' }}>Transcribing...</span>
                  </div>
                )}
                <button
                  type="button"
                  className={`btn-voice ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (isRecording) {
                      stopRecording();
                    } else {
                      startRecording();
                    }
                  }}
                  disabled={loading || isTranscribing || refineLoading}
                  style={{ position: 'static' }}
                >
                  {isRecording ? <Square size={24} /> : isTranscribing ? <div className="loader" style={{ width: 20, height: 20, borderWidth: 2 }} /> : <Mic size={20} />}
                </button>
              </div>
            </div>
          </div>

          {/* Refinement Result Display */}
          {refineResult && (
            <div style={{ marginTop: '20px', padding: '20px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid var(--border)' }}>
              {/* Understanding Summary */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '8px', fontWeight: 600 }}>
                  <Lightbulb size={14} style={{ marginRight: '6px', display: 'inline' }} />
                  AI 需求理解
                </div>
                <div style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#ccc', whiteSpace: 'pre-wrap' }}>
                  <ReactMarkdown>{refineResult.understanding_summary}</ReactMarkdown>
                </div>
              </div>

              {/* Inferred Assumptions */}
              {refineResult.inferred_assumptions && refineResult.inferred_assumptions.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '8px', fontWeight: 600 }}>
                    推断的假设
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.85rem', color: '#aaa' }}>
                    {refineResult.inferred_assumptions.map((assumption, i) => (
                      <li key={i}>{assumption}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Questions */}
              {refineResult.questions && refineResult.questions.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '12px', fontWeight: 600 }}>
                    <HelpCircle size={14} style={{ marginRight: '6px', display: 'inline' }} />
                    需要澄清的问题 ({refineResult.questions.length})
                  </div>
                  {refineResult.questions.map((q, i) => (
                    <div key={q.id || i} style={{ marginBottom: '16px', padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px' }}>
                      <div style={{ fontSize: '0.9rem', fontWeight: 500, marginBottom: '6px', color: '#fff' }}>
                        {q.question}
                      </div>
                      {q.why_asking && (
                        <div style={{ fontSize: '0.75rem', color: '#888', marginBottom: '8px' }}>
                          为什么需要：{q.why_asking}
                        </div>
                      )}
                      {q.suggestions && q.suggestions.length > 0 && (
                        <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '8px' }}>
                          建议：{q.suggestions.join('、')}
                        </div>
                      )}
                      <textarea
                        value={refineAnswers[q.id] || ''}
                        onChange={(e) => setRefineAnswers({...refineAnswers, [q.id]: e.target.value})}
                        placeholder="请输入你的回答..."
                        rows={2}
                        disabled={refineLoading || loading}
                        style={{ width: '100%', padding: '8px', fontSize: '0.85rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)', borderRadius: '6px', color: '#fff' }}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Ready to Compile Indicator */}
              {refineResult.ready_to_compile && (
                <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.3)', marginTop: '16px' }}>
                  <div style={{ fontSize: '0.85rem', color: '#10b981', fontWeight: 500 }}>
                    <CheckCircle2 size={14} style={{ marginRight: '6px', display: 'inline' }} />
                    需求已足够清晰，可以开始创建功能
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" onClick={onClose} disabled={loading || refineLoading}>
              取消
            </button>
            {refineResult && !refineResult.ready_to_compile && refineResult.questions && refineResult.questions.length > 0 && (
              <button
                type="button"
                className="btn-primary"
                disabled={refineLoading || Object.keys(refineAnswers).length === 0}
                onClick={async () => {
                  // Collect answers
                  const feedback = refineResult.questions.map(q => {
                    const answer = refineAnswers[q.id] || '';
                    return `${q.question}\n${answer}`;
                  }).join('\n\n');
                  await handleRefineFeedback(feedback);
                  setRefineAnswers({});
                }}
              >
                {refineLoading ? '分析中...' : '提交回答并继续细化'}
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={loading || refineLoading || !input.trim()}>
              {loading ? '创建中...' : refineResult && refineResult.ready_to_compile ? '创建功能' : '开始分析'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default App;
