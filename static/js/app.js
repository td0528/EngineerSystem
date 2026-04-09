/**
 * VONIKO Factory Management System - Main JavaScript
 */

// API configuration
const API_BASE = '/api';

// API helper
const api = {
    async request(method, endpoint, data = null) {
        const token = localStorage.getItem('token');
        const headers = {
            'Content-Type': 'application/json',
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const options = {
            method,
            headers,
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);

        if (response.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/';
            throw new Error('Unauthorized');
        }

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Request failed');
        }

        return result;
    },

    get(endpoint) {
        return this.request('GET', endpoint);
    },

    post(endpoint, data) {
        return this.request('POST', endpoint, data);
    },

    put(endpoint, data) {
        return this.request('PUT', endpoint, data);
    },

    delete(endpoint) {
        return this.request('DELETE', endpoint);
    },

    async upload(endpoint, formData) {
        const token = localStorage.getItem('token');
        const headers = {};

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers,
            body: formData,
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Upload failed');
        }

        return result;
    }
};

// Authentication check
function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return false;
    }
    return true;
}

// Logout function
function logout() {
    window._isNavigating = true; // prevent beforeunload prompt
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
}

// ===== Close-tab/browser detection =====
// Track internal navigation so we don't prompt when clicking links
window._isNavigating = false;

// Mark all link clicks and form submits as internal navigation
document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href]');
    if (link && !link.getAttribute('href').startsWith('#')) {
        window._isNavigating = true;
    }
});
document.addEventListener('submit', () => { window._isNavigating = true; });

// Show "Leave site?" confirmation when closing tab/browser
window.addEventListener('beforeunload', (e) => {
    if (window._isNavigating) return; // internal navigation, don't prompt
    if (!localStorage.getItem('token')) return; // not logged in, don't prompt

    e.preventDefault();
    e.returnValue = ''; // required for Chrome
});

// Clear login data when actually leaving (tab close confirmed)
window.addEventListener('unload', () => {
    if (window._isNavigating) return; // internal navigation, keep session

    localStorage.removeItem('token');
    localStorage.removeItem('user');
});

// Toast notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${type === 'success'
            ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
            : type === 'error'
                ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
                : '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
        }
        </svg>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Date formatting
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Number formatting – show full number with thousand separators,
// keep decimals only when they exist (no trailing .00), max 4 dp
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    let n = Number(num);
    if (isNaN(n)) return '-';
    // Round to 4 decimal places to eliminate floating-point noise
    n = parseFloat(n.toFixed(4));
    const decStr = String(n).split('.');
    const decimals = decStr.length > 1 ? decStr[1].length : 0;
    return n.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: decimals
    });
}

function formatCurrency(amount, currency = 'VND') {
    if (amount === null || amount === undefined) return '-';
    return `${formatNumber(amount)} ${currency}`;
}

// Modal management
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        // Prevent closing createOrderModal when clicking outside
        if (e.target.id === 'createOrderModal') return;
        e.target.classList.remove('active');
    }
});

// Escape key to close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});

// Dropdown management
document.addEventListener('click', (e) => {
    // Close all dropdowns when clicking outside
    if (!e.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown.active').forEach(dropdown => {
            dropdown.classList.remove('active');
        });
    }
});

function toggleDropdown(element) {
    const dropdown = element.closest('.dropdown');
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Search autocomplete
async function searchMaterials(query, targetElement) {
    if (query.length < 1) {
        targetElement.innerHTML = '';
        targetElement.style.display = 'none';
        return;
    }

    try {
        const results = await api.get(`/materials/search?q=${encodeURIComponent(query)}&limit=10`);

        if (results.length === 0) {
            targetElement.innerHTML = '<div class="dropdown-item">无匹配结果</div>';
        } else {
            targetElement.innerHTML = results.map(item => `
                <div class="dropdown-item" data-id="${item.id}" data-sap="${item.sap_code}" data-name="${item.name_cn}">
                    <strong>${item.sap_code}</strong> - ${item.name_cn}
                    ${item.name_vn ? `<br><small>${item.name_vn}</small>` : ''}
                </div>
            `).join('');
        }

        targetElement.style.display = 'block';
    } catch (error) {
        console.error('Search error:', error);
    }
}

// File upload preview
function previewFile(input, previewElement) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();

        reader.onload = (e) => {
            if (input.files[0].type.startsWith('image/')) {
                previewElement.innerHTML = `<img src="${e.target.result}" alt="Preview" style="max-width: 200px; max-height: 200px; border-radius: var(--radius-md);">`;
            } else {
                previewElement.innerHTML = `<div class="file-preview">${input.files[0].name}</div>`;
            }
        };

        reader.readAsDataURL(input.files[0]);
    }
}

// Mobile sidebar toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// URL query parameter helpers
function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

function setQueryParam(name, value) {
    const params = new URLSearchParams(window.location.search);
    params.set(name, value);
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
}

// Loading state
function showLoading(element) {
    element.innerHTML = '<div class="spinner" style="margin: 2rem auto;"></div>';
}

// Pagination
function renderPagination(total, currentPage, pageSize, container, onPageChange) {
    const totalPages = Math.ceil(total / pageSize);

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '<div style="display: flex; gap: var(--spacing-sm); justify-content: center; margin-top: var(--spacing-lg);">';

    // Previous button
    html += `<button class="btn btn-secondary" ${currentPage === 1 ? 'disabled' : ''} onclick="${onPageChange}(${currentPage - 1})">上一页</button>`;

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button class="btn ${i === currentPage ? 'btn-primary' : 'btn-secondary'}" onclick="${onPageChange}(${i})">${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span style="padding: var(--spacing-sm);">...</span>';
        }
    }

    // Next button
    html += `<button class="btn btn-secondary" ${currentPage === totalPages ? 'disabled' : ''} onclick="${onPageChange}(${currentPage + 1})">下一页</button>`;

    html += '</div>';
    container.innerHTML = html;
}

// Confirm dialog
function confirmDialog(message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.innerHTML = `
            <div class="modal" style="max-width: 400px;">
                <div class="modal-header">
                    <h3>确认</h3>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" id="confirmCancel">取消</button>
                    <button class="btn btn-primary" id="confirmOk">确定</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        overlay.querySelector('#confirmCancel').onclick = () => {
            overlay.remove();
            resolve(false);
        };

        overlay.querySelector('#confirmOk').onclick = () => {
            overlay.remove();
            resolve(true);
        };
    });
}

// Export functions
window.api = api;
window.checkAuth = checkAuth;
window.logout = logout;
window.showToast = showToast;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.formatNumber = formatNumber;
window.formatCurrency = formatCurrency;
window.openModal = openModal;
window.closeModal = closeModal;
window.toggleDropdown = toggleDropdown;
window.debounce = debounce;
window.searchMaterials = searchMaterials;
window.previewFile = previewFile;
window.toggleSidebar = toggleSidebar;
window.getQueryParam = getQueryParam;
window.setQueryParam = setQueryParam;
window.showLoading = showLoading;
window.renderPagination = renderPagination;
window.confirmDialog = confirmDialog;
