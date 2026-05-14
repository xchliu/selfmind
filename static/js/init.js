// 确保 DOM 加载完成后启动轮询 + 初始化标题
document.addEventListener('DOMContentLoaded', function() {
  startPolling();
  // 初始化时加载agent配置，设置页面标题
  if (typeof loadSettingsData === 'function') {
    loadSettingsData();
  }
});