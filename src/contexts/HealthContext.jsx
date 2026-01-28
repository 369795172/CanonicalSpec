import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { checkBackendHealth, startHealthCheckPolling } from '../utils/healthCheck';

const HealthContext = createContext(null);

export const useHealth = () => {
  const context = useContext(HealthContext);
  if (!context) {
    throw new Error('useHealth must be used within a HealthProvider');
  }
  return context;
};

export const HealthProvider = ({ children }) => {
  const [isHealthy, setIsHealthy] = useState(null); // null = 未知, true = 健康, false = 不健康
  const [isChecking, setIsChecking] = useState(true);
  const [error, setError] = useState(null);
  const [lastCheckTime, setLastCheckTime] = useState(null);

  // 执行健康检查
  const performHealthCheck = useCallback(async () => {
    setIsChecking(true);
    const result = await checkBackendHealth();
    
    setIsHealthy(result.healthy);
    setError(result.error || null);
    setLastCheckTime(new Date());
    setIsChecking(false);

    return result.healthy;
  }, []);

  // 初始化时立即检查一次
  useEffect(() => {
    performHealthCheck();
  }, [performHealthCheck]);

  // 启动轮询检查
  useEffect(() => {
    const stopPolling = startHealthCheckPolling((result) => {
      setIsHealthy(result.healthy);
      setError(result.error || null);
      setLastCheckTime(new Date());
      setIsChecking(false);
    });

    return () => {
      stopPolling();
    };
  }, []);

  // 手动触发检查（用于用户点击重试）
  const retryCheck = useCallback(async () => {
    return await performHealthCheck();
  }, [performHealthCheck]);

  const value = {
    isHealthy,
    isChecking,
    error,
    lastCheckTime,
    retryCheck,
  };

  return (
    <HealthContext.Provider value={value}>
      {children}
    </HealthContext.Provider>
  );
};
