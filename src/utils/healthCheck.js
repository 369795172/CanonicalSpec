/**
 * 后端健康检查工具函数
 * 用于检测后端服务和API是否正常运行
 */

const HEALTH_CHECK_ENDPOINT = '/api/v1/system/health';
const HEALTH_CHECK_INTERVAL = 30000; // 30秒检查一次
const HEALTH_CHECK_TIMEOUT = 5000; // 5秒超时

/**
 * 检查后端健康状态
 * @returns {Promise<{healthy: boolean, error?: string, data?: any}>}
 */
export const checkBackendHealth = async () => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT);

    const response = await fetch(HEALTH_CHECK_ENDPOINT, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return {
        healthy: false,
        error: `后端服务响应异常 (HTTP ${response.status})`,
      };
    }

    const data = await response.json();
    
    // 后端返回的status可能是 'healthy' 或 'ok'
    if (data.status === 'healthy' || data.status === 'ok') {
      return {
        healthy: true,
        data: data,
      };
    } else {
      return {
        healthy: false,
        error: `后端服务状态异常: ${data.status || 'unknown'}`,
        data: data,
      };
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      return {
        healthy: false,
        error: '后端服务响应超时，请检查服务是否启动',
      };
    } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return {
        healthy: false,
        error: '无法连接到后端服务，请检查服务是否启动',
      };
    } else {
      return {
        healthy: false,
        error: `健康检查失败: ${error.message}`,
      };
    }
  }
};

/**
 * 创建一个健康检查轮询器
 * @param {Function} onHealthChange - 健康状态变化回调函数
 * @returns {Function} 停止轮询的函数
 */
export const startHealthCheckPolling = (onHealthChange) => {
  let isPolling = true;
  let timeoutId = null;

  const poll = async () => {
    if (!isPolling) return;

    const result = await checkBackendHealth();
    onHealthChange(result);

    if (isPolling) {
      timeoutId = setTimeout(poll, HEALTH_CHECK_INTERVAL);
    }
  };

  // 立即执行一次
  poll();

  // 返回停止函数
  return () => {
    isPolling = false;
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  };
};

export { HEALTH_CHECK_INTERVAL };
