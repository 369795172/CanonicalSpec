import React from 'react';
import { AlertTriangle, RefreshCw, CheckCircle2, Loader } from 'lucide-react';
import { useHealth } from '../contexts/HealthContext';
import './HealthStatusBanner.css';

const HealthStatusBanner = () => {
  const { isHealthy, isChecking, error, retryCheck } = useHealth();

  // 如果健康状态未知或正在检查，不显示横幅
  if (isHealthy === null || isChecking) {
    return null;
  }

  // 如果健康，不显示横幅（或者可以显示一个小的成功指示器）
  if (isHealthy) {
    return null;
  }

  // 不健康时显示错误横幅
  return (
    <div className="health-status-banner health-status-banner--error">
      <div className="health-status-banner__content">
        <AlertTriangle size={20} className="health-status-banner__icon" />
        <div className="health-status-banner__message">
          <strong>后端服务连接失败</strong>
          <span>{error || '无法连接到后端服务'}</span>
        </div>
        <button
          className="health-status-banner__retry"
          onClick={retryCheck}
          disabled={isChecking}
          title="重试连接"
        >
          {isChecking ? (
            <Loader size={16} className="spinning" />
          ) : (
            <RefreshCw size={16} />
          )}
          重试
        </button>
      </div>
    </div>
  );
};

export default HealthStatusBanner;
