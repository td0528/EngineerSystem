/**
 * i18n 国际化支持
 * 用户可通过编辑 translations 对象添加/修改翻译词条
 */

const i18n = {
    currentLang: (function () {
        const urlLang = new URLSearchParams(window.location.search).get('lang');
        if (urlLang && ['cn', 'vn'].includes(urlLang)) {
            localStorage.setItem('lang', urlLang);
            return urlLang;
        }
        return localStorage.getItem('lang') || 'cn';
    })(),

    // 翻译词条 - 用户可在此维护
    translations: {
        cn: {
            // 通用
            'app.title': 'VONIKO 工厂管理系统',
            'common.loading': '加载中...',
            'common.save': '保存',
            'common.cancel': '取消',
            'common.delete': '删除',
            'common.edit': '编辑',
            'common.add': '新增',
            'common.search': '搜索',
            'common.filter': '筛选',
            'common.export': '导出Excel',
            'common.import': '导入数据',
            'common.all': '全部',
            'common.confirm': '确认',
            'common.success': '成功',
            'common.failed': '失败',
            'common.noData': '暂无数据',

            // 导航
            'nav.overview': '概览',
            'nav.procurement': '采购与库存',
            'nav.workManagement': '工作管理',
            'nav.resources': '资源中心',
            'nav.system': '系统',
            'nav.dashboard': '仪表盘',
            'nav.materials': '物料管理',
            'nav.orders': '采购订单',
            'nav.warehouse': '仓库管理',
            'nav.stockAlerts': '库存预警',
            'nav.tasks': '任务系统',
            'nav.records': '记录功能',
            'nav.documents': '资料管理',
            'nav.devices': '设备监控',
            'nav.supplierPortal': '供应商门户',
            'nav.users': '用户管理',
            'nav.logout': '退出登录',
            'nav.settings': '系统设置',

            // 物料管理
            'materials.title': '物料管理',
            'materials.addMaterial': '新增物料',
            'materials.sapCode': 'SAP号码',
            'materials.nameCn': '中文名称',
            'materials.category': '种类',
            'materials.subcategory': '细分类别',
            'materials.workshop': '车间',
            'materials.equipment': '使用设备',
            'materials.location': '库位',
            'materials.minStock': '最低库存',
            'materials.image': '图片',
            'materials.actions': '操作',
            'materials.priceHistory': '价格历史',
            'materials.viewTrend': '查看走势',

            // 采购订单
            'orders.title': '采购订单管理',
            'orders.createOrder': '新建采购订单',
            'orders.poNumber': 'PO号',
            'orders.orderDate': '采购日期',
            'orders.supplier': '供应商',
            'orders.materialName': '物料名称',
            'orders.quantity': '数量',
            'orders.unitPrice': '单价',
            'orders.subtotal': '小计',
            'orders.status': '状态',
            'orders.itemStatus': '物料状态',
            'orders.arrivalDate': '到货时间',
            'orders.total': '总金额',

            // 状态
            'status.draft': '草稿',
            'status.submitted': '已提交',
            'status.confirmed': '已确认',
            'status.partialReceived': '部分到货',
            'status.completed': '已完成',
            'status.cancelled': '已取消',

            // 分类
            'category.electrical': '电气',
            'category.mechanical': '机械',
            'category.mold': '模具',
            'category.consumable': '耗材',

            // 车间
            'workshop.mainLine': '主线',
            'workshop.positive': '正极',
            'workshop.negative': '负极',
            'workshop.accessories': '配件',
            'workshop.general': '通用',

            // 配置维护
            'config.title': '配置维护',
            'config.subcategory': '细分类别',
            'config.equipment': '使用设备',
            'config.workshop': '车间',
            'config.addNew': '添加新项',
            'config.syncFromOrders': '从订单同步',
            'config.syncFromMaterials': '从物料同步',

            // 仪表盘
            'dashboard.title': '仪表盘',
            'dashboard.welcome': '欢迎回来',
            'dashboard.overview': '系统概览',
            'dashboard.totalMaterials': '物料总数',
            'dashboard.pendingOrders': '待处理订单',
            'dashboard.lowStock': '库存不足',
            'dashboard.completedTasks': '已完成任务',
            'dashboard.recentOrders': '最近订单',
            'dashboard.stockAlerts': '库存预警',
            'dashboard.quickActions': '快捷操作',

            // 仓库管理
            'warehouse.title': '仓库管理',
            'warehouse.inbound': '入库',
            'warehouse.outbound': '出库',
            'warehouse.inventory': '库存盘点',
            'warehouse.location': '库位管理',
            'warehouse.currentStock': '当前库存',
            'warehouse.stockHistory': '库存记录',

            // 库存预警
            'stockAlerts.title': '库存预警',
            'stockAlerts.critical': '紧急',
            'stockAlerts.warning': '警告',
            'stockAlerts.low': '偏低',
            'stockAlerts.normal': '正常',
            'stockAlerts.belowMin': '低于最低库存',
            'stockAlerts.items': '条物料需要补充',

            // 按钮和操作
            'btn.addMaterial': '添加物料',
            'btn.importData': '导入数据',
            'btn.exportExcel': '导出Excel',
            'btn.config': '配置',
            'btn.view': '查看',
            'btn.edit': '编辑',
            'btn.delete': '删除',
            'btn.refresh': '刷新',
            'btn.clear': '清空',
            'btn.submit': '提交',

            // 表格
            'table.noData': '暂无数据',
            'table.loading': '加载中...',
            'table.selectAll': '全选',
            'table.items': '条物料',
        },
        vn: {
            // 通用
            'app.title': 'Hệ thống quản lý nhà máy VONIKO',
            'common.loading': 'Đang tải...',
            'common.save': 'Lưu',
            'common.cancel': 'Hủy',
            'common.delete': 'Xóa',
            'common.edit': 'Sửa',
            'common.add': 'Thêm',
            'common.search': 'Tìm kiếm',
            'common.filter': 'Lọc',
            'common.export': 'Xuất Excel',
            'common.import': 'Nhập dữ liệu',
            'common.all': 'Tất cả',
            'common.confirm': 'Xác nhận',
            'common.success': 'Thành công',
            'common.failed': 'Thất bại',
            'common.noData': 'Không có dữ liệu',

            // 导航
            'nav.overview': 'Tổng quan',
            'nav.procurement': 'Mua sắm & Kho',
            'nav.workManagement': 'Quản lý công việc',
            'nav.resources': 'Trung tâm tài nguyên',
            'nav.system': 'Hệ thống',
            'nav.dashboard': 'Bảng điều khiển',
            'nav.materials': 'Quản lý vật liệu',
            'nav.orders': 'Đơn đặt hàng',
            'nav.warehouse': 'Quản lý kho',
            'nav.stockAlerts': 'Cảnh báo tồn kho',
            'nav.tasks': 'Hệ thống nhiệm vụ',
            'nav.records': 'Hồ sơ',
            'nav.documents': 'Quản lý tài liệu',
            'nav.devices': 'Giám sát thiết bị',
            'nav.supplierPortal': 'Cổng thông tin nhà cung cấp',
            'nav.users': 'Quản lý người dùng',
            'nav.logout': 'Đăng xuất',
            'nav.settings': 'Cài đặt hệ thống',

            // 物料管理
            'materials.title': 'Quản lý vật liệu',
            'materials.addMaterial': 'Thêm vật liệu',
            'materials.sapCode': 'Mã SAP',
            'materials.nameCn': 'Tên tiếng Trung',
            'materials.category': 'Loại',
            'materials.subcategory': 'Phân loại chi tiết',
            'materials.workshop': 'Phân xưởng',
            'materials.equipment': 'Thiết bị sử dụng',
            'materials.location': 'Vị trí kho',
            'materials.minStock': 'Tồn kho tối thiểu',
            'materials.image': 'Hình ảnh',
            'materials.actions': 'Thao tác',
            'materials.priceHistory': 'Lịch sử giá',
            'materials.viewTrend': 'Xem xu hướng',

            // 采购订单
            'orders.title': 'Quản lý đơn đặt hàng',
            'orders.createOrder': 'Tạo đơn đặt hàng mới',
            'orders.poNumber': 'Số PO',
            'orders.orderDate': 'Ngày đặt hàng',
            'orders.supplier': 'Nhà cung cấp',
            'orders.materialName': 'Tên vật liệu',
            'orders.quantity': 'Số lượng',
            'orders.unitPrice': 'Đơn giá',
            'orders.subtotal': 'Thành tiền',
            'orders.status': 'Trạng thái',
            'orders.itemStatus': 'Trạng thái vật liệu',
            'orders.arrivalDate': 'Ngày đến hàng',
            'orders.total': 'Tổng tiền',

            // 状态
            'status.draft': 'Bản nháp',
            'status.submitted': 'Đã gửi',
            'status.confirmed': 'Đã xác nhận',
            'status.partialReceived': 'Nhận một phần',
            'status.completed': 'Hoàn thành',
            'status.cancelled': 'Đã hủy',

            // 分类
            'category.electrical': 'Điện',
            'category.mechanical': 'Cơ khí',
            'category.mold': 'Khuôn',
            'category.consumable': 'Vật tư tiêu hao',

            // 车间
            'workshop.mainLine': 'Dây chuyền chính',
            'workshop.positive': 'Cực dương',
            'workshop.negative': 'Cực âm',
            'workshop.accessories': 'Phụ kiện',
            'workshop.general': 'Chung',

            // 配置维护
            'config.title': 'Cấu hình',
            'config.subcategory': 'Phân loại chi tiết',
            'config.equipment': 'Thiết bị',
            'config.workshop': 'Phân xưởng',
            'config.addNew': 'Thêm mục mới',
            'config.syncFromOrders': 'Đồng bộ từ đơn hàng',
            'config.syncFromMaterials': 'Đồng bộ từ vật liệu',

            // 仪表盘
            'dashboard.title': 'Bảng điều khiển',
            'dashboard.welcome': 'Chào mừng trở lại',
            'dashboard.overview': 'Tổng quan hệ thống',
            'dashboard.totalMaterials': 'Tổng số vật liệu',
            'dashboard.pendingOrders': 'Đơn hàng chờ xử lý',
            'dashboard.lowStock': 'Thiếu hàng tồn kho',
            'dashboard.completedTasks': 'Nhiệm vụ hoàn thành',
            'dashboard.recentOrders': 'Đơn hàng gần đây',
            'dashboard.stockAlerts': 'Cảnh báo tồn kho',
            'dashboard.quickActions': 'Thao tác nhanh',

            // 仓库管理
            'warehouse.title': 'Quản lý kho',
            'warehouse.inbound': 'Nhập kho',
            'warehouse.outbound': 'Xuất kho',
            'warehouse.inventory': 'Kiểm kê kho',
            'warehouse.location': 'Quản lý vị trí',
            'warehouse.currentStock': 'Tồn kho hiện tại',
            'warehouse.stockHistory': 'Lịch sử kho',

            // 库存预警
            'stockAlerts.title': 'Cảnh báo tồn kho',
            'stockAlerts.critical': 'Khẩn cấp',
            'stockAlerts.warning': 'Cảnh báo',
            'stockAlerts.low': 'Thấp',
            'stockAlerts.normal': 'Bình thường',
            'stockAlerts.belowMin': 'Dưới mức tối thiểu',
            'stockAlerts.items': 'vật liệu cần bổ sung',

            // 按钮和操作
            'btn.addMaterial': 'Thêm vật liệu',
            'btn.importData': 'Nhập dữ liệu',
            'btn.exportExcel': 'Xuất Excel',
            'btn.config': 'Cấu hình',
            'btn.view': 'Xem',
            'btn.edit': 'Sửa',
            'btn.delete': 'Xóa',
            'btn.refresh': 'Làm mới',
            'btn.clear': 'Xóa',
            'btn.submit': 'Gửi',

            // 表格
            'table.noData': 'Không có dữ liệu',
            'table.loading': 'Đang tải...',
            'table.selectAll': 'Chọn tất cả',
            'table.items': 'vật liệu',
        }
    },

    // 获取翻译
    t(key) {
        const lang = this.translations[this.currentLang];
        return lang[key] || this.translations.cn[key] || key;
    },

    // 切换语言
    setLang(lang) {
        this.currentLang = lang;
        localStorage.setItem('lang', lang);
        this.updatePage();
        this.updateSidebarLangText();

        // Dispatch storage event for other tabs
        window.dispatchEvent(new StorageEvent('storage', {
            key: 'lang',
            newValue: lang
        }));

        // Dispatch custom event for current page
        window.dispatchEvent(new CustomEvent('lang-change', { detail: lang }));

        // Reload page with query param to ensure persistence and full refresh
        // This is more robust than just reload() as it carries state in URL
        window._isNavigating = true;
        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.location.href = url.toString();
    },

    // 更新页面所有带 data-i18n 属性的元素
    updatePage() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.textContent = this.t(key);
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = this.t(key);
        });
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = this.t(key);
        });
        // 更新语言按钮状态
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.lang === this.currentLang);
        });
    },

    // 更新侧边栏语言按钮文字
    updateSidebarLangText() {
        const langText = document.getElementById('langToggleText');
        if (langText) {
            // Check if it's the top bar toggle (flag only) or old sidebar one
            if (langText.parentElement.id === 'langBtn') {
                langText.textContent = this.currentLang === 'vn' ? '🇻🇳' : '🇨🇳';
            } else {
                langText.textContent = this.currentLang === 'vn' ? '🇻🇳 VN → CN' : '🇨🇳 CN → VN';
            }
        }
    },

    // 导出翻译词条到Excel
    exportToExcel() {
        const rows = [['Key', 'Chinese', 'Vietnamese']];
        const cnTrans = this.translations.cn;
        const vnTrans = this.translations.vn;
        const allKeys = new Set([...Object.keys(cnTrans), ...Object.keys(vnTrans)]);

        allKeys.forEach(key => {
            rows.push([key, cnTrans[key] || '', vnTrans[key] || '']);
        });

        // Convert to CSV
        const csv = rows.map(row => row.map(cell => `"${(cell || '').replace(/"/g, '""')}"`).join(',')).join('\n');
        const BOM = '\uFEFF';
        const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translations.csv';
        a.click();
        URL.revokeObjectURL(url);
    },

    // 从Excel导入翻译词条
    importFromExcel(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            const lines = text.split('\n').filter(l => l.trim());
            const header = lines[0];

            // Skip header row
            for (let i = 1; i < lines.length; i++) {
                const row = lines[i].match(/(".*?"|[^",]+)(?=,|$)/g);
                if (row && row.length >= 3) {
                    const key = row[0].replace(/^"|"$/g, '').replace(/""/g, '"');
                    const cn = row[1].replace(/^"|"$/g, '').replace(/""/g, '"');
                    const vn = row[2].replace(/^"|"$/g, '').replace(/""/g, '"');

                    if (key && key !== 'Key') {
                        if (cn) this.translations.cn[key] = cn;
                        if (vn) this.translations.vn[key] = vn;
                    }
                }
            }

            this.updatePage();
            alert('导入成功！共导入 ' + (lines.length - 1) + ' 条词条');
        };
        reader.readAsText(file);
    },

    // 初始化
    init() {
        // Check URL param first to fix state loss issues
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang && ['cn', 'vn'].includes(urlLang)) {
            if (urlLang !== localStorage.getItem('lang')) {
                localStorage.setItem('lang', urlLang);
            }
            this.currentLang = urlLang;
        }

        this.updatePage();
        this.updateSidebarLangText();
    }
};

// 全局翻译函数
function t(key) {
    return i18n.t(key);
}

// 切换语言函数
function toggleLang() {
    const newLang = i18n.currentLang === 'cn' ? 'vn' : 'cn';
    i18n.setLang(newLang);
}

// 导出翻译
function exportTranslations() {
    i18n.exportToExcel();
}

// 导入翻译
function importTranslations() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.xlsx';
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
            i18n.importFromExcel(file);
        }
    };
    input.click();
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    i18n.init();
});

// Expose i18n to window for sidebar.js access
window.i18n = i18n;
