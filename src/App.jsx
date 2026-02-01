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
import GenomeStatus from './components/GenomeStatus';
import GenomeChanges from './components/GenomeChanges';
import HealthStatusBanner from './components/HealthStatusBanner';
import { useHealth } from './contexts/HealthContext';

const App = () => {
  const { isHealthy } = useHealth();
  const [features, setFeatures] = useState(() => {
    const saved = localStorage.getItem('canonical_features');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentFeature, setCurrentFeature] = useState(null);
  const [newFeatureInput, setNewFeatureInput] = useState(() => {
    const saved = localStorage.getItem('canonical_draft_input');
    return saved || '';
  });
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('list'); // 'list', 'create', 'view'
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false); // History list collapsed by default
  
  // 当后端不健康时，禁用所有操作
  const isDisabled = isHealthy === false;
  
  // Clarification mode state
  const [clarifyingMode, setClarifyingMode] = useState(false);
  const [clarifyingFeatureId, setClarifyingFeatureId] = useState(null); // null = 新建，有值 = 编辑已有
  const [refineResult, setRefineResult] = useState(null);
  
  // Debug: Track refineResult changes
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:45',message:'refineResult state changed',data:{hasRefineResult:!!refineResult,readyToCompile:refineResult?.ready_to_compile,round:refineResult?.round,hasGenome:!!refineResult?.genome},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
    // #endregion
    
    // Scroll to result area when refineResult updates
    if (refineResult && clarifyingMode) {
      setTimeout(() => {
        const resultElement = document.querySelector('.clarification-content');
        if (resultElement) {
          resultElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    }
  }, [refineResult, clarifyingMode]);
  const [refineContext, setRefineContext] = useState({
    conversation_history: [],
    round: 0,
    feature_id: null,
    additional_context: {}
  });
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineAnswers, setRefineAnswers] = useState({});
  const [currentView, setCurrentView] = useState('current'); // 'current' or history index
  const [bypassLimit, setBypassLimit] = useState(false); // Allow user to bypass clarification limit
  
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

  // 自动保存输入到 localStorage
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:72',message:'newFeatureInput state changed',data:{newFeatureInputLength:newFeatureInput?.length,newFeatureInputValue:newFeatureInput?.substring(0,50),willSaveToLocalStorage:!!newFeatureInput.trim()},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    if (newFeatureInput.trim()) {
      localStorage.setItem('canonical_draft_input', newFeatureInput);
    } else {
      localStorage.removeItem('canonical_draft_input');
    }
  }, [newFeatureInput]);

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
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      return;
    }
    
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
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      alert('后端服务不可用，无法进行语音转文字');
      return;
    }
    
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.webm');
      
      const response = await fetch('/api/v1/transcribe', {
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
    
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      alert('后端服务不可用，无法创建功能');
      return;
    }
    
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
          localStorage.removeItem('canonical_draft_input');
        }
      }
    } catch (err) {
      console.error('Failed to create feature:', err);
      alert('创建功能失败，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  };

  // Refine functions
  const handleRefine = async () => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:293',message:'handleRefine called',data:{clarifyingFeatureId,newFeatureInputLength:newFeatureInput?.length,newFeatureInputValue:newFeatureInput?.substring(0,50),isHealthy},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    // For existing features, allow empty input (will load from spec)
    if (!clarifyingFeatureId && !newFeatureInput.trim()) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:296',message:'handleRefine early return - empty input',data:{clarifyingFeatureId,newFeatureInputTrimmed:newFeatureInput.trim()},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      return;
    }
    
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:300',message:'handleRefine early return - backend unhealthy',data:{isHealthy},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      alert('后端服务不可用，无法进行需求分析');
      return;
    }
    
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:304',message:'handleRefine before API call',data:{endpoint:clarifyingFeatureId?`/api/v1/features/${clarifyingFeatureId}/refine`:'/api/v1/refine',inputLength:newFeatureInput?.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    setRefineLoading(true);
    try {
      const endpoint = clarifyingFeatureId 
        ? `/api/v1/features/${clarifyingFeatureId}/refine`
        : '/api/v1/refine';
      
      const body = clarifyingFeatureId && !newFeatureInput.trim()
        ? { context: refineContext }  // No input needed for existing feature
        : { input: newFeatureInput, context: refineContext };
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:316',message:'handleRefine API request',data:{endpoint,bodyInputLength:body.input?.length,hasContext:!!body.context},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:323',message:'handleRefine API response',data:{status:res.status,ok:res.ok},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      
      if (res.ok) {
        const data = await res.json();
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:327',message:'handleRefine API success - before setState',data:{hasData:!!data,hasGenome:!!data.genome,round:data.round,readyToCompile:data.ready_to_compile,hasUnderstandingSummary:!!data.understanding_summary,understandingSummaryLength:data.understanding_summary?.length,hasQuestions:!!data.questions,questionsCount:data.questions?.length,hasInferredAssumptions:!!data.inferred_assumptions,inferredAssumptionsCount:data.inferred_assumptions?.length,dataKeys:Object.keys(data)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        
        setRefineResult(data);
        // Update context with new conversation history and genome
        setRefineContext(prev => ({
          ...prev,
          conversation_history: [
            ...prev.conversation_history,
            { role: 'user', content: newFeatureInput },
            { role: 'assistant', content: JSON.stringify(data) }
          ],
          round: data.round || prev.round + 1,
          feature_id: clarifyingFeatureId || prev.feature_id,
          additional_context: {
            ...prev.additional_context,
            genome: data.genome || prev.additional_context?.genome
          }
        }));
        
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:343',message:'handleRefine API success - after setState',data:{newFeatureInputLength:newFeatureInput?.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
      } else {
        const error = await res.json();
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:346',message:'handleRefine API error',data:{status:res.status,errorDetail:error.detail},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
        alert(`需求分析失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:351',message:'handleRefine exception',data:{errorMessage:err.message,errorStack:err.stack?.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      console.error('Failed to refine requirement:', err);
      alert('需求分析失败，请重试');
    } finally {
      setRefineLoading(false);
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:355',message:'handleRefine finally - loading set to false',data:{newFeatureInputLength:newFeatureInput?.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
    }
  };

  const handleRefineFeedback = async (feedback) => {
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      alert('后端服务不可用，无法处理反馈');
      return false;
    }
    
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
          round: data.round || prev.round + 1,
          additional_context: {
            ...prev.additional_context,
            genome: data.genome || prev.additional_context?.genome
          }
        }));
        return true;
      } else {
        // 尝试解析错误信息
        let errorMessage = '未知错误';
        try {
          const error = await res.json();
          errorMessage = error.detail || error.message || `HTTP ${res.status}`;
        } catch (e) {
          errorMessage = `HTTP ${res.status}: ${res.statusText}`;
        }
        alert(`反馈处理失败: ${errorMessage}`);
        return false;
      }
    } catch (err) {
      console.error('Failed to apply feedback:', err);
      alert('反馈处理失败，请重试');
      return false;
    } finally {
      setRefineLoading(false);
    }
  };

  const handleSubmitRefined = async () => {
    if (!refineResult || !refineResult.ready_to_compile) return;
    
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      alert('后端服务不可用，无法创建功能');
      return;
    }
    
    setLoading(true);
    try {
      const endpoint = clarifyingFeatureId
        ? `/api/v1/features/${clarifyingFeatureId}/compile`
        : '/api/v1/run';
      
      const body = clarifyingFeatureId
        ? { refine_result: refineResult }
        : { input: newFeatureInput, refine_result: refineResult };
      
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.feature_id) {
          await fetchFeatures();
          // Reset clarification state
          setClarifyingMode(false);
          setClarifyingFeatureId(null);
          setRefineResult(null);
          setRefineContext({
            conversation_history: [],
            round: 0,
            feature_id: null,
            additional_context: {}
          });
          setRefineAnswers({});
          setNewFeatureInput('');
          localStorage.removeItem('canonical_draft_input');
          
          // Navigate to feature view
          setCurrentFeature(data.feature_id);
          setActiveTab('view');
        }
      } else {
        const error = await res.json();
        alert(`创建功能失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      console.error('Failed to create feature:', err);
      alert('创建功能失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleStartClarification = (featureId = null) => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:520',message:'handleStartClarification called',data:{featureId,newFeatureInputLength:newFeatureInput?.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
    setClarifyingFeatureId(featureId);
    setClarifyingMode(true);
    setRefineResult(null);
    setRefineContext({
      conversation_history: [],
      round: 0,
      feature_id: featureId,
      additional_context: {}
    });
    setRefineAnswers({});
    setCurrentView('current');
    setBypassLimit(false); // Reset bypass flag
    
    // If editing existing feature, load it immediately
    if (featureId) {
      // Trigger refine to load existing feature data
      setTimeout(() => {
        handleRefine();
      }, 100);
    }
  };

  const handleCancelClarification = () => {
    setClarifyingMode(false);
    setClarifyingFeatureId(null);
    setRefineResult(null);
    setRefineContext({
      conversation_history: [],
      round: 0,
      feature_id: null,
      additional_context: {}
    });
    setRefineAnswers({});
    setBypassLimit(false); // Reset bypass flag
    setCurrentView('current');
    setNewFeatureInput('');
  };

  const currentDisplayData = activeTab === 'view' && currentFeature
    ? features.find(f => f.feature_id === currentFeature)
    : null;

  return (
    <div className={`app-container ${isHealthy === false ? 'app-container--has-banner' : ''}`}>
      <HealthStatusBanner />
      <header>
        <div className="logo">
          Canonical Spec <span>Manager</span>
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <button
            className="btn-create"
            onClick={() => handleStartClarification(null)}
            disabled={isDisabled}
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
          {/* Inline Clarification View */}
          {clarifyingMode && (
            <div className="clarification-pane" style={{ padding: '20px' }}>
              {/* Header with back button and status */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                <button
                  onClick={handleCancelClarification}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'transparent', border: 'none', color: 'var(--text)', cursor: 'pointer', fontSize: '0.9rem' }}
                >
                  <ChevronRight size={20} style={{ transform: 'rotate(180deg)' }} />
                  返回
                </button>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
                  {clarifyingFeatureId ? `编辑: ${clarifyingFeatureId}` : '创建新功能'}
                </div>
              </div>

              {/* Input Form */}
              <form onSubmit={(e) => {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:553',message:'form onSubmit triggered',data:{newFeatureInputLength:newFeatureInput?.length,hasRefineResult:!!refineResult,readyToCompile:refineResult?.ready_to_compile},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
                e.preventDefault();
                if (refineResult && refineResult.ready_to_compile) {
                  handleSubmitRefined();
                } else {
                  handleRefine();
                }
              }} style={{ marginBottom: '20px' }}>
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
                    value={newFeatureInput}
                    onChange={(e) => {
                      // #region agent log
                      fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:580',message:'textarea onChange',data:{newValueLength:e.target.value?.length,newValuePreview:e.target.value?.substring(0,30)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
                      // #endregion
                      setNewFeatureInput(e.target.value);
                    }}
                    placeholder="描述你想实现的功能，例如：我想做一个健身网站"
                    rows={6}
                    disabled={loading || isRecording || refineLoading || isDisabled}
                    style={{ 
                      width: '100%', 
                      paddingLeft: isRecording ? '240px' : '12px', 
                      paddingRight: '80px',
                      paddingTop: '12px',
                      paddingBottom: '12px',
                      fontSize: '0.9rem',
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      color: 'var(--text)',
                      resize: 'vertical'
                    }}
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
                      disabled={loading || isTranscribing || refineLoading || isDisabled}
                      style={{ position: 'static' }}
                    >
                      {isRecording ? <Square size={24} /> : isTranscribing ? <div className="loader" style={{ width: 20, height: 20, borderWidth: 2 }} /> : <Mic size={20} />}
                    </button>
                  </div>
                </div>
              </form>

              {/* Refinement Result Display */}
              {refineResult && (() => {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:627',message:'Rendering refineResult',data:{hasRefineResult:!!refineResult,readyToCompile:refineResult?.ready_to_compile,currentView},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
                // #endregion
                // Determine which data to display based on currentView
                let displayData = refineResult;
                
                if (currentView !== 'current' && refineResult.genome?.history) {
                  const historyIndex = parseInt(currentView);
                  const history = refineResult.genome.history.slice().reverse();
                  if (history[historyIndex]) {
                    const snapshot = history[historyIndex];
                    displayData = {
                      ...refineResult,
                      understanding_summary: snapshot.summary,
                      round: snapshot.round,
                    };
                  }
                }
                
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e4f07afd-e2d6-4325-b413-c366657f19d5',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:694',message:'Display data prepared',data:{hasUnderstandingSummary:!!displayData.understanding_summary,understandingSummaryLength:displayData.understanding_summary?.length,understandingSummaryPreview:displayData.understanding_summary?.substring(0,100),hasQuestions:!!displayData.questions,questionsCount:displayData.questions?.length,questions:displayData.questions?.map(q=>({id:q.id,question:q.question?.substring(0,50)})),hasInferredAssumptions:!!displayData.inferred_assumptions,inferredAssumptionsCount:displayData.inferred_assumptions?.length,inferredAssumptions:displayData.inferred_assumptions?.map(a=>a.substring(0,50)),round:displayData.round,readyToCompile:displayData.ready_to_compile},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
                // #endregion
                
                return (
                  <div className="clarification-content" style={{ marginTop: '20px', width: '100%', display: 'flex', gap: '20px' }}>
                    {/* Main Content Area */}
                    <div className="clarification-main" style={{ flex: 1, padding: '20px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '2px solid var(--accent)', width: '100%', minHeight: '200px' }}>
                      {/* Update indicator */}
                      <div style={{ padding: '12px', background: 'rgba(44, 107, 237, 0.4)', borderRadius: '6px', marginBottom: '15px', border: '2px solid var(--accent)', color: '#fff', fontWeight: 'bold', fontSize: '0.95rem', boxShadow: '0 0 10px rgba(44, 107, 237, 0.5)' }}>
                        <div style={{ marginBottom: '8px' }}>✓ 第 {displayData.round} 轮分析结果</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 'normal', opacity: 0.9 }}>
                          {displayData.questions && displayData.questions.length > 0 && (
                            <div>• 需要回答 {displayData.questions.length} 个问题</div>
                          )}
                          {displayData.inferred_assumptions && displayData.inferred_assumptions.length > 0 && (
                            <div>• 推断出 {displayData.inferred_assumptions.length} 个假设</div>
                          )}
                          {displayData.ready_to_compile && (
                            <div style={{ color: '#10b981', marginTop: '4px' }}>• ✓ 可以开始创建功能</div>
                          )}
                        </div>
                      </div>
                      
                      {/* Changes Highlight */}
                      {currentView === 'current' && refineResult.changes && <GenomeChanges changes={refineResult.changes} />}
                      
                      {/* Understanding Summary */}
                      <div style={{ marginBottom: '20px', width: '100%' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: '8px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span>
                            <Lightbulb size={14} style={{ marginRight: '6px', display: 'inline' }} />
                            AI 需求理解
                          </span>
                          <span style={{ fontSize: '0.7rem', color: '#888', fontWeight: 400 }}>
                            第 {displayData.round} 轮
                          </span>
                        </div>
                        <div style={{ fontSize: '0.9rem', lineHeight: '1.6', color: '#fff', whiteSpace: 'pre-wrap', minHeight: '40px', padding: '12px', background: 'rgba(0,0,0,0.4)', borderRadius: '6px', border: '1px solid rgba(44, 107, 237, 0.5)' }}>
                          {displayData.understanding_summary ? (
                            <div style={{ color: '#fff' }}>
                              <ReactMarkdown>{displayData.understanding_summary}</ReactMarkdown>
                            </div>
                          ) : (
                            <div style={{ color: '#888', fontStyle: 'italic' }}>暂无需求理解内容</div>
                          )}
                        </div>
                      </div>

                      {/* Inferred Assumptions */}
                      {currentView === 'current' && displayData.inferred_assumptions && displayData.inferred_assumptions.length > 0 && (
                        <div style={{ marginBottom: '20px', padding: '15px', background: 'rgba(255, 170, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(255, 170, 68, 0.3)' }}>
                          <div style={{ fontSize: '0.8rem', color: 'var(--exploration)', marginBottom: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <Lightbulb size={14} />
                            推断的假设 ({displayData.inferred_assumptions.length})
                          </div>
                          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.9rem', color: '#fff', lineHeight: '1.8' }}>
                            {displayData.inferred_assumptions.map((assumption, i) => (
                              <li key={i} style={{ marginBottom: '8px' }}>{assumption}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Questions */}
                      {currentView === 'current' && displayData.questions && displayData.questions.length > 0 && (
                        <div style={{ marginBottom: '20px', padding: '15px', background: 'rgba(255, 170, 68, 0.15)', borderRadius: '8px', border: '2px solid rgba(255, 170, 68, 0.4)' }}>
                          <div style={{ fontSize: '0.8rem', color: 'var(--exploration)', marginBottom: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <HelpCircle size={16} />
                            需要澄清的问题 ({displayData.questions.length})
                          </div>
                          {displayData.questions.map((q, i) => (
                            <div key={q.id || i} style={{ marginBottom: '16px', padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid rgba(255, 170, 68, 0.3)' }}>
                              <div style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '8px', color: '#fff' }}>
                                {i + 1}. {q.question}
                              </div>
                              {q.why_asking && (
                                <div style={{ fontSize: '0.8rem', color: '#aaa', marginBottom: '8px', paddingLeft: '20px', fontStyle: 'italic' }}>
                                  为什么需要：{q.why_asking}
                                </div>
                              )}
                              {q.suggestions && q.suggestions.length > 0 && (
                                <div style={{ fontSize: '0.8rem', color: '#888', marginBottom: '10px', paddingLeft: '20px' }}>
                                  建议：{q.suggestions.join('、')}
                                </div>
                              )}
                              <textarea
                                value={refineAnswers[q.id] || ''}
                                onChange={(e) => setRefineAnswers({...refineAnswers, [q.id]: e.target.value})}
                                placeholder="请输入你的回答..."
                                rows={3}
                                disabled={refineLoading || loading || isDisabled}
                                style={{ width: '100%', padding: '10px', fontSize: '0.9rem', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border)', borderRadius: '6px', color: '#fff' }}
                              />
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Ready to Compile Indicator */}
                      {currentView === 'current' && displayData.ready_to_compile && (
                        <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.3)', marginTop: '16px' }}>
                          <div style={{ fontSize: '0.85rem', color: '#10b981', fontWeight: 500 }}>
                            <CheckCircle2 size={14} style={{ marginRight: '6px', display: 'inline' }} />
                            需求已足够清晰，可以开始创建功能
                          </div>
                        </div>
                      )}
                      
                      {/* Limit Reached Indicator */}
                      {currentView === 'current' && refineResult && refineResult.genome && (
                        (() => {
                          const round = refineResult.genome.round || refineResult.round || 0;
                          const totalQuestions = refineResult.genome.history?.reduce((sum, h) => sum + (h.questions_asked?.length || 0), 0) || 0;
                          const currentQuestions = refineResult.questions?.length || 0;
                          const MAX_ROUNDS = 5;
                          const MAX_TOTAL_QUESTIONS = 10;
                          const isAtLimit = round >= MAX_ROUNDS || (totalQuestions + currentQuestions) >= MAX_TOTAL_QUESTIONS;
                          const limitReason = round >= MAX_ROUNDS 
                            ? `已达到最大轮次限制（${MAX_ROUNDS}轮）`
                            : (totalQuestions + currentQuestions) >= MAX_TOTAL_QUESTIONS
                            ? `已达到最大问题数限制（${MAX_TOTAL_QUESTIONS}个）`
                            : null;
                          
                          // Check if ready_to_compile was forced by limit (check understanding_summary for limit message)
                          const summaryHasLimit = refineResult.understanding_summary?.includes('限制') || refineResult.understanding_summary?.includes('⚠️');
                          const isLimitForced = isAtLimit && (summaryHasLimit || refineResult.ready_to_compile);
                          
                          if (isLimitForced && !bypassLimit) {
                            return (
                              <div style={{ padding: '12px', background: 'rgba(255, 170, 68, 0.15)', borderRadius: '8px', border: '1px solid rgba(255, 170, 68, 0.4)', marginTop: '16px' }}>
                                <div style={{ fontSize: '0.85rem', color: '#ffaa44', fontWeight: 500, marginBottom: '8px' }}>
                                  <HelpCircle size={14} style={{ marginRight: '6px', display: 'inline' }} />
                                  {limitReason}
                                </div>
                                <div style={{ fontSize: '0.8rem', color: '#aaa', marginBottom: '10px' }}>
                                  建议进入编译阶段，或继续澄清以获取更多信息。
                                </div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <button
                                    onClick={() => setBypassLimit(true)}
                                    style={{ padding: '6px 12px', background: 'rgba(255, 170, 68, 0.2)', border: '1px solid rgba(255, 170, 68, 0.4)', borderRadius: '6px', color: '#ffaa44', cursor: 'pointer', fontSize: '0.8rem' }}
                                  >
                                    继续澄清
                                  </button>
                                  <button
                                    onClick={handleSubmitRefined}
                                    style={{ padding: '6px 12px', background: 'var(--accent)', border: 'none', borderRadius: '6px', color: '#fff', cursor: 'pointer', fontSize: '0.8rem' }}
                                  >
                                    进入编译
                                  </button>
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()
                      )}
                    </div>
                    
                    {/* Sidebar - Genome Status */}
                    {refineResult.genome && (
                      <div className="clarification-sidebar">
                        <GenomeStatus 
                          genome={refineResult.genome} 
                          currentView={currentView}
                          onViewChange={setCurrentView}
                        />
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px', paddingTop: '20px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
                <button 
                  onClick={handleCancelClarification} 
                  disabled={loading || refineLoading || isDisabled}
                  style={{ padding: '10px 20px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text)', cursor: 'pointer' }}
                >
                  取消
                </button>
                {refineResult && !refineResult.ready_to_compile && refineResult.questions && refineResult.questions.length > 0 && (
                  <button
                    onClick={async () => {
                      const feedback = refineResult.questions.map(q => {
                        const answer = refineAnswers[q.id] || '';
                        return `${q.question}\n${answer}`;
                      }).join('\n\n');
                      
                      // 检查是否有空答案
                      const hasEmptyAnswers = refineResult.questions.some(q => !refineAnswers[q.id] || refineAnswers[q.id].trim() === '');
                      if (hasEmptyAnswers) {
                        alert('请填写所有问题的答案');
                        return;
                      }
                      
                      const success = await handleRefineFeedback(feedback);
                      // 只在成功时才清空答案，失败时保留用户输入
                      if (success) {
                        setRefineAnswers({});
                        setBypassLimit(false); // Reset bypass flag after successful feedback
                      }
                    }}
                    disabled={refineLoading || Object.keys(refineAnswers).length === 0 || isDisabled}
                    style={{ padding: '10px 20px', background: 'var(--accent)', border: 'none', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 500 }}
                  >
                    {refineLoading ? '分析中...' : '提交回答并继续细化'}
                  </button>
                )}
                {refineResult && refineResult.ready_to_compile && (
                  <button 
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleSubmitRefined();
                    }}
                    disabled={loading || refineLoading || isDisabled}
                    style={{ padding: '10px 20px', background: 'var(--accent)', border: 'none', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 500 }}
                  >
                    {loading ? '创建中...' : '创建功能'}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* History minimized by default - show only toggle button */}
          {!clarifyingMode && activeTab === 'list' && !isHistoryExpanded && (
            <div className="history-minimized">
              <div className="welcome-section">
                <Sparkles size={48} style={{ marginBottom: '20px', color: 'var(--accent)' }} />
                <h2>欢迎使用 Canonical Spec</h2>
                <p>点击"创建功能"开始创建新的需求规范</p>
              </div>
              {features.length > 0 && (
                <button 
                  className="btn-history-toggle"
                  onClick={() => setIsHistoryExpanded(true)}
                >
                  <History size={16} />
                  查看历史功能 ({features.length})
                </button>
              )}
            </div>
          )}

          {/* History expanded - show full list */}
          {!clarifyingMode && activeTab === 'list' && isHistoryExpanded && (
            <div className="history-expanded">
              <button 
                className="btn-history-collapse"
                onClick={() => setIsHistoryExpanded(false)}
              >
                <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
                收起历史
              </button>
              <div className="features-list">
                {features.map((feature, index) => {
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
                        if (feature.status === 'clarifying') {
                          handleStartClarification(feature.feature_id);
                        } else {
                          setCurrentFeature(feature.feature_id);
                          setActiveTab('view');
                        }
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
                        {feature.spec?.spec?.goal || '点击查看详情'}
                      </p>
                      {feature.status === 'clarifying' && (
                        <div className="clarifying-indicator">
                          <HelpCircle size={14} />
                          <span>需要补充信息</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!clarifyingMode && activeTab === 'view' && currentDisplayData && (
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
                onClick={() => handleStartClarification(null)}
                disabled={isDisabled}
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
            disabled={loading || isRecording || clarifyingMode || isDisabled}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !loading && !isRecording && !clarifyingMode && newFeatureInput.trim()) {
                e.preventDefault();
                handleStartClarification(null);
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
              disabled={loading || isTranscribing || isDisabled}
              title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Start voice input"}
            >
              {isRecording ? <Square size={24} /> : isTranscribing ? <div className="loader" style={{ width: 20, height: 20, borderWidth: 2 }} /> : <Mic size={20} />}
            </button>
          </div>
        </div>
        <button
          className="btn-generate"
          onClick={() => {
            if (clarifyingMode) {
              if (refineResult && refineResult.ready_to_compile) {
                handleSubmitRefined();
              } else {
                handleRefine();
              }
            } else {
              handleStartClarification(null);
            }
          }}
          disabled={(loading || isRecording || refineLoading) || (!clarifyingMode && !newFeatureInput.trim()) || (clarifyingMode && !newFeatureInput.trim() && !refineResult) || isDisabled}
        >
          {(loading || refineLoading) ? <div className="loader" style={{ width: 24, height: 24, borderWidth: 2 }} /> : <Sparkles size={32} />}
        </button>
      </div>


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

// Clarification Panel Component (kept for FeatureDetailView compatibility)
const ClarificationPanel = ({ questions, answers, setAnswers, onSubmit, isSubmitting }) => {
  const { isHealthy } = useHealth();
  const isDisabled = isHealthy === false;
  
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
            disabled={isDisabled}
          />
        </div>
      ))}
      <button 
        onClick={onSubmit} 
        disabled={isSubmitting || Object.keys(answers).length === 0 || isDisabled}
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
  const { isHealthy } = useHealth();
  const [featureData, setFeatureData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clarifyQuestions, setClarifyQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [generatingDoc, setGeneratingDoc] = useState(false);
  
  // 当后端不健康时，禁用所有操作
  const isDisabled = isHealthy === false;

  useEffect(() => {
    fetchFeatureDetails();
  }, [featureId, isHealthy]);

  useEffect(() => {
    if (featureData?.gate_result?.clarify_questions) {
      setClarifyQuestions(featureData.gate_result.clarify_questions);
    } else {
      setClarifyQuestions([]);
    }
    setAnswers({});
  }, [featureData]);

  const fetchFeatureDetails = async () => {
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      setLoading(false);
      return;
    }
    
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
    // 如果后端不健康，不执行API调用
    if (isHealthy === false) {
      alert('后端服务不可用，无法提交答案');
      return;
    }
    
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

  const handleGenerateDocument = async () => {
    if (isHealthy === false) {
      alert('后端服务不可用，无法生成文档');
      return;
    }
    
    setGeneratingDoc(true);
    try {
      const res = await fetch(`/api/v1/features/${featureId}/document`, {
        method: 'GET',
      });
      
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: '未知错误' }));
        alert(`生成文档失败: ${error.detail || '未知错误'}`);
        return;
      }
      
      // Get filename from Content-Disposition header or use default
      const contentDisposition = res.headers.get('Content-Disposition');
      let filename = `${featureId}_spec.md`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      // Get blob data
      const blob = await res.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.style.display = 'none';
      
      // Append to body and trigger click
      document.body.appendChild(a);
      
      // Use setTimeout to ensure the element is in the DOM
      setTimeout(() => {
        a.click();
        
        // Clean up after download starts
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }, 100);
      }, 0);
      
      // Show success message
      setTimeout(() => {
        alert(`文档已开始下载！\n\n文件名：${filename}\n文件将保存到浏览器的默认下载位置（通常是 ~/Downloads 文件夹）。`);
      }, 200);
      
    } catch (err) {
      console.error('Failed to generate document:', err);
      alert(`生成文档失败: ${err.message || '请重试'}`);
    } finally {
      setGeneratingDoc(false);
    }
  };

  const handlePublishToFeishu = async () => {
    if (isHealthy === false) {
      alert('后端服务不可用，无法同步到飞书');
      return;
    }
    
    if (feature?.status !== 'executable_ready') {
      alert('功能状态必须是 executable_ready 才能发布到飞书');
      return;
    }
    
    if (!confirm('确定要同步到飞书多维表格吗？')) {
      return;
    }
    
    setPublishing(true);
    try {
      const res = await fetch(`/api/v1/features/${featureId}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        alert(`同步成功！\n操作: ${data.operation}\n外部ID: ${data.external_id}\n${data.message}`);
        // Refresh feature data
        fetchFeatureDetails();
      } else {
        const error = await res.json();
        alert(`同步失败: ${error.detail || '未知错误'}`);
      }
    } catch (err) {
      console.error('Failed to publish to Feishu:', err);
      alert('同步到飞书失败，请重试');
    } finally {
      setPublishing(false);
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
        <div className="feature-actions" style={{ display: 'flex', gap: '10px', marginLeft: 'auto' }}>
          <button
            className="btn-action"
            onClick={handleGenerateDocument}
            disabled={isDisabled || generatingDoc}
            style={{
              padding: '8px 16px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: isDisabled || generatingDoc ? 'not-allowed' : 'pointer',
              opacity: isDisabled || generatingDoc ? 0.5 : 1,
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            {generatingDoc ? '生成中...' : '生成文档'}
          </button>
          <button
            className="btn-action"
            onClick={handlePublishToFeishu}
            disabled={isDisabled || publishing || feature?.status !== 'executable_ready'}
            style={{
              padding: '8px 16px',
              backgroundColor: feature?.status === 'executable_ready' ? '#10b981' : '#888',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: (isDisabled || publishing || feature?.status !== 'executable_ready') ? 'not-allowed' : 'pointer',
              opacity: (isDisabled || publishing || feature?.status !== 'executable_ready') ? 0.5 : 1,
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            {publishing ? '同步中...' : '同步到飞书'}
          </button>
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
                  <p style={{ whiteSpace: 'pre-wrap' }}>{spec.spec?.goal || '暂无'}</p>
                </div>
                {spec.spec?.non_goals && spec.spec.non_goals.length > 0 && (
                  <div className="spec-item">
                    <strong>非目标：</strong>
                    <ul>
                      {spec.spec.non_goals.map((goal, i) => (
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


export default App;
