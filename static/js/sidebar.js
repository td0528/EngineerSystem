/**
 * Sidebar component - loaded into all pages
 * Includes collapsible sidebar and i18n support
 */
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    const currentPage = window.location.pathname.split('/').pop().replace('.html', '');

    // Get current language from URL first, then localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const currentLang = urlParams.get('lang') || localStorage.getItem('lang') || 'cn';

    // Sync localStorage with URL param
    if (urlParams.get('lang') && urlParams.get('lang') !== localStorage.getItem('lang')) {
        localStorage.setItem('lang', urlParams.get('lang'));
    }

    const isLight = localStorage.getItem('theme') === 'light';
    if (isLight) {
        document.documentElement.classList.add('light-mode');
    }

    // Check if sidebar should be collapsed (from localStorage)
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (sidebarCollapsed) {
        document.documentElement.classList.add('sidebar-collapsed');
    }

    // Expose toggle function globally
    window.toggleTheme = function () {
        const html = document.documentElement;
        html.classList.toggle('light-mode');
        const isLightMode = html.classList.contains('light-mode');
        localStorage.setItem('theme', isLightMode ? 'light' : 'dark');

        // Update icon
        const icon = document.getElementById('themeIcon');
        if (icon) {
            icon.innerHTML = isLightMode ? getMoonIcon() : getSunIcon();
        }
    };

    // Toggle sidebar collapse
    window.toggleSidebar = function () {
        document.documentElement.classList.toggle('sidebar-collapsed');
        const isCollapsed = document.documentElement.classList.contains('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
    };

    function getSunIcon() {
        return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>`;
    }

    function getMoonIcon() {
        return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>`;
    }

    function getMenuIcon() {
        return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>`;
    }

    sidebar.innerHTML = `
        <div class="sidebar-header">
            <div class="sidebar-row-1">
                <button class="sidebar-toggle" type="button" onclick="toggleSidebar()" title="Toggle Sidebar">
                    ${getMenuIcon()}
                </button>
                <div class="sidebar-brand">
                    <div class="battery-indicator">
                        <div class="battery-level">
                            <div class="battery-fill" style="width: 85%;"></div>
                        </div>
                    </div>
                    <h1>VONIKO</h1>
                </div>
            </div>
            <div class="sidebar-row-2">
                <button class="theme-toggle" type="button" onclick="toggleLang()" id="langBtn" title="切换语言">
                    <span id="langToggleText" style="font-size: 14px;">${currentLang === 'vn' ? '🇻🇳' : '🇨🇳'}</span>
                </button>
                <button class="theme-toggle" type="button" onclick="toggleTheme()" id="themeBtn" title="切换主题">
                    <div id="themeIcon">${isLight ? getMoonIcon() : getSunIcon()}</div>
                </button>
            </div>
        </div>
        
        <nav class="sidebar-nav">
            <div class="nav-section">
                <div class="nav-section-title" data-i18n="nav.overview">概览</div>
                <a href="/static/dashboard.html" class="nav-item ${currentPage === 'dashboard' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="7" height="9" rx="1"/>
                        <rect x="14" y="3" width="7" height="5" rx="1"/>
                        <rect x="14" y="12" width="7" height="9" rx="1"/>
                        <rect x="3" y="16" width="7" height="5" rx="1"/>
                    </svg>
                    <span data-i18n="nav.dashboard">仪表盘</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title" data-i18n="nav.procurement">采购与库存</div>
                <a href="/static/materials.html" class="nav-item ${currentPage === 'materials' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
                        <line x1="7" y1="7" x2="7.01" y2="7"/>
                    </svg>
                    <span data-i18n="nav.materials">物料管理</span>
                </a>
                <a href="/static/orders.html" class="nav-item ${currentPage === 'orders' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16c0 1.1.9 2 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
                        <path d="M14 3v5h5M16 13H8M16 17H8M10 9H8"/>
                    </svg>
                    <span data-i18n="nav.orders">采购订单</span>
                </a>
                <a href="/static/warehouse.html" class="nav-item ${currentPage === 'warehouse' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                        <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                    <span data-i18n="nav.warehouse">仓库管理</span>
                </a>
                <a href="/static/stock-alerts.html" class="nav-item ${currentPage === 'stock-alerts' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    <span data-i18n="nav.stockAlerts">库存预警</span>
                </a>
                <a href="/static/supplier-admin.html" class="nav-item ${currentPage === 'supplier-admin' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                    <span>供应商管理</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title" data-i18n="nav.workManagement">工作管理</div>
                <a href="/static/tasks.html" class="nav-item ${currentPage === 'tasks' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    <span data-i18n="nav.tasks">任务系统</span>
                </a>
                <a href="/static/records.html" class="nav-item ${currentPage === 'records' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9"/>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                    </svg>
                    <span data-i18n="nav.records">记录功能</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title" data-i18n="nav.resources">资源中心</div>
                <a href="/static/documents.html" class="nav-item ${currentPage === 'documents' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                    <span data-i18n="nav.documents">资料管理</span>
                </a>
                <a href="/static/devices.html" class="nav-item ${currentPage === 'devices' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="4" y="4" width="16" height="16" rx="2"/>
                        <rect x="9" y="9" width="6" height="6"/>
                        <line x1="9" y1="1" x2="9" y2="4"/>
                        <line x1="15" y1="1" x2="15" y2="4"/>
                        <line x1="9" y1="20" x2="9" y2="23"/>
                        <line x1="15" y1="20" x2="15" y2="23"/>
                    </svg>
                    <span data-i18n="nav.devices">设备监控</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title" data-i18n="nav.system">系统</div>
                <a href="/static/users.html" class="nav-item ${currentPage === 'users' ? 'active' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                        <circle cx="9" cy="7" r="4"/>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                    </svg>
                    <span data-i18n="nav.users">用户管理</span>
                </a>

                <a href="#" class="nav-item" onclick="logout(); return false;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    <span data-i18n="nav.logout">退出登录</span>
                </a>
            </div>
        </nav>
    `;

    // CRITICAL: Update translations AFTER sidebar is rendered
    // Use setTimeout to ensure i18n.js has initialized
    setTimeout(function () {
        if (window.i18n && typeof window.i18n.updatePage === 'function') {
            // Ensure i18n currentLang is set from URL first
            const urlLang = new URLSearchParams(window.location.search).get('lang');
            if (urlLang && ['cn', 'vn'].includes(urlLang)) {
                window.i18n.currentLang = urlLang;
                localStorage.setItem('lang', urlLang);
            } else if (localStorage.getItem('lang')) {
                window.i18n.currentLang = localStorage.getItem('lang');
            }
            window.i18n.updatePage();
        }
    }, 10);
});
