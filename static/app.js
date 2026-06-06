// =============================================================================
// app.js — Guns & Reloading v1.0
// =============================================================================
// SECTION MAP
//   1.  Canvas / range-session state          (~L10)
//   2.  UI state trackers                     (~L25)
//   3.  Toast, mobile menu, collection filter (~L49)
//   4.  Photo replacement & sell modal        (~L96)
//   5.  Form helpers & datalist               (~L183)
//   6.  Lookup data & scope select            (~L252)
//   7.  Tab & pane switching                  (~L308)
//   8.  Inventory loaders (catalog, TC, scopes, ammo, components) (~L370)
//   9.  Component cards & grouped renders     (~L526)
//  10.  Component CRUD (qty update, delete)   (~L671)
//  11.  Scope mount editor                    (~L770)
//  12.  Add-form category/ammo-type switching (~L930)
//  13.  Threshold settings panel              (~L964)
//  14.  Range session / canvas engine         (~L1006)
//  15.  Crop modal                            (~L1215)
//  16.  Form submit handlers                  (~L1784)
//  17.  Preferences & init                    (~L2200)
// =============================================================================

const canvas = document.getElementById('target-canvas');
const ctx = canvas ? canvas.getContext('2d') : null;
let imgElement = new Image();

let groups = []; 
let currentGroupShots = []; 
let state = "idle"; 
let calibrationPoints = [];
let pixelsPerInch = null;

let liveBoxDims = { w: 300, h: 150 };

let liveBoxPos = { x: 0, y: 0, customized: false };
let isDraggingBox = false;
let isDraggingLabelIdx = null;
let dragOffset = { x: 0, y: 0 };
let isMultiTouch = false;
let touchStartClientPos = null;
let touchHandled = false;

// Crop modal state
let pendingGroupData = null;
let cropRect = { x: 0, y: 0, w: 0, h: 0 };
let cropDisplayScale = 1;
let cropDragState = { active: false, mode: null, startX: 0, startY: 0, origRect: null };

// UI Pipeline Filters state trackers
let currentCollectionFilter = "active"; // "active" or "sold"
let activeItemIdForSaleLog = null;
let activeItemIdForPictureReplacement = null;
let currentInventoryTab = "platforms";
let currentAmmoFilter = "factory";
let currentPlatformTab = "general"; // "general", "shotgun", "handgun", or "tc"
function currentFrameType() {
    return { general: 'Rifle', shotgun: 'Shotgun', handgun: 'Pistol' }[currentPlatformTab] || 'Rifle';
}
let currentComponentFilter = "powders"; // "powders", "primers", "bullets"

let lookupTables = {
    firearm_brands: [],
    firearm_models: [],
    optics: [],
    furniture: [],
    ammo_brands: [],
    calibers: [],
    powders: [],
    primers: [],
    bullets: [],
    brass: []
};

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `p-4 rounded-lg shadow-xl text-xs font-bold tracking-wide border transition-all duration-300 transform translate-y-2 opacity-0 flex items-center space-x-2 pointer-events-auto max-w-sm ${
        type === 'error' 
        ? 'bg-red-950/90 text-red-400 border-red-800' 
        : 'bg-gray-850/95 text-emerald-400 border-emerald-800'
    }`;
    
    toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✅'}</span><span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.remove('opacity-0', 'translate-y-2'), 50);
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function toggleMobileMenu() {
    const panel = document.getElementById('mobile-menu-panel');
    const overlay = document.getElementById('mobile-menu-overlay');
    const isOpen = !panel.classList.contains('-translate-x-full');
    if (isOpen) {
        panel.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
    } else {
        panel.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
    }
}

// Vault Filtering Controllers
function setCollectionFilter() {
    currentCollectionFilter = currentCollectionFilter === 'sold' ? 'active' : 'sold';
    const btnSold = document.getElementById('btn-filter-sold');
    if (btnSold) {
        btnSold.className = currentCollectionFilter === 'sold'
            ? "px-3 py-1 rounded bg-gray-800 text-emerald-400 cursor-pointer"
            : "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    }
    if (currentPlatformTab === 'tc') loadTCInventory();
    else loadCatalog();
}

// Picture Swap Trigger
function triggerPictureReplacement(itemId) {
    activeItemIdForPictureReplacement = itemId;
    const replacer = document.getElementById('global-picture-replacer');
    if (replacer) replacer.click();
}

async function processPictureReplacement(inputElement) {
    const file = inputElement.files[0];
    if (!file || !activeItemIdForPictureReplacement) return;

    const formData = new FormData();
    formData.append('image_1', file);

    try {
        const response = await fetch(`/firearms/${activeItemIdForPictureReplacement}/update-photo/`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showToast("Vault record profile image modified successfully.");
            loadCatalog();
        } else {
            const fakeUrl = URL.createObjectURL(file);
            localStorage.setItem(`local_img_${activeItemIdForPictureReplacement}`, fakeUrl);
            showToast("Profile image applied locally.");
            loadCatalog();
        }
    } catch(e) {
        const fakeUrl = URL.createObjectURL(file);
        localStorage.setItem(`local_img_${activeItemIdForPictureReplacement}`, fakeUrl);
        showToast("Applied image update profile locally.", "success");
        loadCatalog();
    }
    inputElement.value = "";
}

// Sale Modal Controller Interfaces
function openSellModal(itemId, currentTitle) {
    activeItemIdForSaleLog = itemId;
    const titleEl = document.getElementById('sell-modal-item-title');
    const priceEl = document.getElementById('modal-sold-price');
    const modalEl = document.getElementById('sell-modal');
    
    if (titleEl) titleEl.innerText = currentTitle;
    if (priceEl) priceEl.value = "";
    if (modalEl) modalEl.classList.remove('hidden');
}

function closeSellModal() {
    const modalEl = document.getElementById('sell-modal');
    if (modalEl) modalEl.classList.add('hidden');
    activeItemIdForSaleLog = null;
}

async function submitAssetSale() {
    const soldPrice = parseFloat(document.getElementById('modal-sold-price').value);
    if (isNaN(soldPrice) || soldPrice < 0) {
        showToast("Please check parameters. Input a valid sold valuation.", "error");
        return;
    }

    try {
        const response = await fetch(`/firearms/${activeItemIdForSaleLog}/mark-sold/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_sold: true, price_sold: soldPrice })
        });

        if (response.ok) {
            showToast("Asset status moved to Sold Registry.");
            closeSellModal();
            loadCatalog();
        } else {
            showToast("Failed to log sale. Server returned an error.", "error");
        }
    } catch(err) {
        showToast("Failed to log sale. Check your connection and try again.", "error");
    }
}

function handleBrandOrModelChange() {
    const brandEl = document.getElementById('rifle-brand-input') || document.getElementById('rifle-brand-select');
    const modelEl = document.getElementById('rifle-model-input') || document.getElementById('rifle-model-select');
    if (!brandEl || !modelEl) return;

    const brandVal = brandEl.value.trim().toLowerCase();
    const modelVal = modelEl.value.trim().toLowerCase();
    const barrelOption = document.getElementById('tc-barrel-only-option');
    const extPanel = document.getElementById('tc-modular-extension');
    const frameSelect = document.getElementById('rifle-frame-select');
    
    const opticContainer = document.getElementById('optic-dropdown-container');
    const furnitureContainer = document.getElementById('furniture-dropdown-container');

    const isTC = (brandVal === "thompson/center" || brandVal === "thompson center" || brandVal === "tc");
    const isModularModel = (modelVal === "encore" || modelVal === "contender");

    if (barrelOption && frameSelect) {
        if (isTC && isModularModel) {
            barrelOption.classList.remove('hidden');
        } else {
            barrelOption.classList.add('hidden');
            if (frameSelect.value === "Barrel Only") frameSelect.value = "Rifle";
        }
    }

    if (frameSelect) {
        // 🌟 FIXED LOGIC: Only show the modular matrix extension if it's explicitly a "Barrel Only" framework type
        if (frameSelect.value === "Barrel Only") {
            if (opticContainer) opticContainer.classList.add('hidden');
            if (furnitureContainer) furnitureContainer.classList.add('hidden');
            if (extPanel && isTC) extPanel.classList.remove('hidden');
        } else {
            if (opticContainer) opticContainer.classList.remove('hidden');
            if (furnitureContainer) furnitureContainer.classList.remove('hidden');
            if (extPanel) extPanel.classList.add('hidden'); // 👈 Force hidden for standard rifles/pistols
        }
    }
}

function handleFrameTypeChange() { handleBrandOrModelChange(); }

function toggleScopeInputState() {
    const toggleEl = document.getElementById('tc-scope-installed-toggle');
    if (!toggleEl) return;
    const toggle = toggleEl.value;
    const scopeBox = document.getElementById('tc-scope-specification-box');
    const scopeInput = document.getElementById('tc-scope-name-input');

    if (!scopeBox || !scopeInput) return;

    if (toggle === "Yes") {
        scopeBox.classList.remove('opacity-40');
        const label = scopeBox.querySelector('label');
        if (label) label.className = "block text-xs text-amber-400 mb-1";
        scopeInput.removeAttribute('disabled');
        scopeInput.setAttribute('required', 'required');
        scopeInput.className = "w-full bg-gray-700 border border-gray-600 rounded p-2 text-sm text-white focus:outline-none focus:border-amber-500";
    } else {
        scopeBox.classList.add('opacity-40');
        const label = scopeBox.querySelector('label');
        if (label) label.className = "block text-xs text-gray-500 mb-1";
        scopeInput.setAttribute('disabled', 'disabled');
        scopeInput.removeAttribute('required');
        scopeInput.value = "";
        scopeInput.className = "w-full bg-gray-750 border border-gray-650 rounded p-2 text-sm text-white focus:outline-none";
    }
}

async function fetchInitialLookupData() {
    try {
        const res = await fetch('/lookups/');
        if (!res.ok) return;
        const data = await res.json();
        // Populate datalists
        Object.entries(data).forEach(([cat, values]) => {
            const id = 'dl-' + cat.replace(/_/g, '-');
            const dl = document.getElementById(id);
            if (dl) dl.innerHTML = values.map(v => `<option value="${escHtml(v)}">`).join('');
        });
        // Also populate handload-powder/primer/bullet/brass from inventory names
        if (data.powder_name) {
            const dl = document.getElementById('dl-handload-powder');
            if (dl) dl.innerHTML = data.powder_name.map(v => `<option value="${escHtml(v)}">`).join('');
        }
        if (data.primer_brand) {
            const dl = document.getElementById('dl-handload-primer');
            if (dl) dl.innerHTML = data.primer_brand.map(v => `<option value="${escHtml(v)}">`).join('');
        }
        if (data.bullet_brand) {
            const dl = document.getElementById('dl-handload-bullet');
            if (dl) dl.innerHTML = data.bullet_brand.map(v => `<option value="${escHtml(v)}">`).join('');
        }
        if (data.casing_brand) {
            const dl = document.getElementById('dl-handload-brass');
            if (dl) dl.innerHTML = data.casing_brand.map(v => `<option value="${escHtml(v)}">`).join('');
        }
        // Update the scope select in the firearm form
        populateScopeSelect();
    } catch (err) { console.error('fetchInitialLookupData error:', err); }
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function saveLookupValue(category, value) {
    if (!value || !value.trim()) return;
    const fd = new FormData();
    fd.set('value', value.trim());
    try { await fetch(`/lookups/${category}`, { method: 'POST', body: fd }); } catch(_) {}
}

async function populateScopeSelect() {
    const sel = document.getElementById('rifle-optic-select');
    if (!sel) return;
    try {
        const res = await fetch('/scopes/');
        if (!res.ok) return;
        const scopes = await res.json();
        sel.innerHTML = '<option value="None">None (Iron Sights)</option>' +
            scopes.map(s => `<option value="${s.id}">${s.brand} ${s.model}</option>`).join('');
    } catch(_) {}
}

function switchTab(tabId) {
    const catTab = document.getElementById('catalog-tab');
    const measTab = document.getElementById('measure-tab');
    const addTab = document.getElementById('add-tab');

    if (catTab) catTab.classList.add('hidden');
    if (measTab) measTab.classList.add('hidden');
    if (addTab) addTab.classList.add('hidden');

    const target = document.getElementById(tabId);
    if (target) target.classList.remove('hidden');

    if (tabId === 'catalog-tab') switchInventoryTab(currentInventoryTab);
    if (tabId === 'measure-tab') setupMeasureDropdowns();
}

function switchInventoryTab(tab) {
    currentInventoryTab = tab;
    const tabs = ['platforms', 'optics', 'ammo', 'components'];
    tabs.forEach(t => {
        document.getElementById(`inv-pane-${t}`)?.classList.add('hidden');
        const btn = document.getElementById(`inv-btn-${t}`);
        if (btn) btn.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    });
    document.getElementById(`inv-pane-${tab}`)?.classList.remove('hidden');
    const activeBtn = document.getElementById(`inv-btn-${tab}`);
    if (activeBtn) activeBtn.className = "px-3 py-1 rounded bg-gray-800 text-amber-500 cursor-pointer";

    if (tab === 'platforms')   switchPlatformTab(currentPlatformTab);
    if (tab === 'optics')      loadScopes();
    if (tab === 'ammo')        loadAmmoInventory(currentAmmoFilter);
    if (tab === 'components')  loadComponentInventory(currentComponentFilter);
}

function switchPlatformTab(tab) {
    currentPlatformTab = tab;
    const genPane = document.getElementById('plat-pane-general');
    const tcPane  = document.getElementById('plat-pane-tc');
    const filter  = document.getElementById('plat-collection-filter');
    const firearmTabs = ['general', 'shotgun', 'handgun'];

    firearmTabs.forEach(t => {
        const btn = document.getElementById(`plat-btn-${t}`);
        if (btn) btn.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    });
    const tcBtn = document.getElementById('plat-btn-tc');

    if (tab === 'tc') {
        genPane?.classList.add('hidden');
        tcPane?.classList.remove('hidden');
        if (tcBtn) tcBtn.className = "px-3 py-1 rounded bg-gray-800 text-amber-500 cursor-pointer";
        loadTCInventory();
    } else {
        genPane?.classList.remove('hidden');
        tcPane?.classList.add('hidden');
        if (tcBtn) tcBtn.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
        const activeBtn = document.getElementById(`plat-btn-${tab}`);
        if (activeBtn) activeBtn.className = "px-3 py-1 rounded bg-gray-800 text-amber-500 cursor-pointer";
        loadCatalog(currentFrameType());
    }
}

async function loadTCInventory() {
    const recContainer = document.getElementById('tc-receivers-container');
    const barContainer = document.getElementById('tc-barrels-container');
    if (!recContainer || !barContainer) return;

    try {
        const [recRes, barRes] = await Promise.all([fetch('/tc-receivers/'), fetch('/tc-barrels/')]);
        const allReceivers = recRes.ok ? await recRes.json() : [];
        const barrels      = barRes.ok ? await barRes.json() : [];
        const receivers    = allReceivers.filter(r => currentCollectionFilter === 'sold' ? r.is_sold : !r.is_sold);

        const total = receivers.length + barrels.length;
        document.getElementById('inventory-count').innerText = `${total} TC Item${total !== 1 ? 's' : ''} Registered`;

        if (receivers.length === 0) {
            recContainer.innerHTML = '<p class="text-gray-500 italic text-sm col-span-3">No receivers registered.</p>';
        } else {
            recContainer.innerHTML = receivers.map(r => {
                const soldBadge = r.is_sold
                    ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-950 text-red-400 border border-red-800">SOLD</span>`
                    : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">RECEIVER</span>`;
                const imgHtml = r.image_path
                    ? `<img src="${r.image_path}" class="w-full h-full object-cover">`
                    : `<div class="w-full h-full flex items-center justify-center text-4xl">🛠️</div>`;
                return `
                <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-xl">
                    <div class="w-full h-36 bg-gray-950 overflow-hidden">${imgHtml}</div>
                    <div class="p-3 space-y-2">
                        <div class="flex justify-between items-center">${soldBadge}
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-gray-900 text-gray-300 border border-gray-700">${r.platform}</span>
                        </div>
                        <p class="text-sm font-bold text-white">${r.platform} Receiver</p>
                        <p class="text-xs text-gray-400">S/N: <span class="text-gray-200 font-mono">${r.serial_number || '—'}</span></p>
                        <p class="text-xs text-gray-400">Cost: <span class="text-white font-mono">$${parseFloat(r.price_paid || 0).toFixed(2)}</span></p>
                    </div>
                </div>`;
            }).join('');
        }

        if (barrels.length === 0) {
            barContainer.innerHTML = '<p class="text-gray-500 italic text-sm col-span-3">No barrels registered.</p>';
        } else {
            barContainer.innerHTML = barrels.map(b => {
                const imgHtml = b.image_path
                    ? `<img src="${b.image_path}" class="w-full h-full object-cover">`
                    : `<div class="w-full h-full flex items-center justify-center text-4xl">🎯</div>`;
                const flags = [b.is_threaded && 'Threaded', b.has_muzzle_brake && 'Brake'].filter(Boolean).join(' · ');
                return `
                <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-xl hover:border-blue-400/60 transition">
                    <div class="w-full h-36 bg-gray-950 overflow-hidden">${imgHtml}</div>
                    <div class="p-3 space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800">BARREL</span>
                            <span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800">${b.caliber}</span>
                        </div>
                        <p class="text-sm font-bold text-white">${b.tc_platform} · ${b.caliber}</p>
                        <div class="text-xs text-gray-400 space-y-0.5">
                            ${b.barrel_length ? `<p>Length: <span class="text-gray-200">${b.barrel_length}</span></p>` : ''}
                            ${b.twist_rate    ? `<p>Twist: <span class="text-gray-200 font-mono">${b.twist_rate}</span></p>` : ''}
                            ${b.hardware_color ? `<p>Finish: <span class="text-gray-200">${b.hardware_color}</span></p>` : ''}
                            ${flags ? `<p class="text-gray-500">${flags}</p>` : ''}
                        </div>
                        <p class="text-xs text-gray-400 border-t border-gray-700 pt-1">Cost: <span class="text-white font-mono">$${parseFloat(b.price_paid || 0).toFixed(2)}</span></p>
                    </div>
                </div>`;
            }).join('');
        }
    } catch(err) {
        recContainer.innerHTML = '<p class="text-red-400 italic text-sm col-span-3">Failed to load TC inventory.</p>';
    }
}

function switchAddForm(formId) {
    document.querySelectorAll('.add-platform-form').forEach(f => f.classList.add('hidden'));
    document.getElementById({
        'add-general': 'firearm-form',
        'add-shotgun': 'shotgun-form',
        'add-handgun': 'handgun-form',
        'add-tc-receiver': 'tc-receiver-form',
        'add-tc-barrel': 'tc-barrel-form',
        'add-scope': 'add-scope-form',
    }[formId])?.classList.remove('hidden');

    const btnMap = { 'add-general': 'btn-add-general', 'add-shotgun': 'btn-add-shotgun', 'add-handgun': 'btn-add-handgun', 'add-tc-receiver': 'btn-add-tc-receiver', 'add-tc-barrel': 'btn-add-tc-barrel', 'add-scope': 'btn-add-scope' };
    Object.entries(btnMap).forEach(([key, btnId]) => {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.className = key === formId
            ? "px-3 py-1.5 text-xs font-bold rounded bg-amber-600 text-white cursor-pointer"
            : "px-3 py-1.5 text-xs font-bold rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    });
}

function switchAmmoFilter(type) {
    currentAmmoFilter = type;
    const factBtn = document.getElementById('ammo-btn-factory');
    const handBtn = document.getElementById('ammo-btn-handload');
    if (type === 'factory') {
        if (factBtn) factBtn.className = "px-3 py-1 rounded bg-gray-800 text-blue-400 cursor-pointer";
        if (handBtn) handBtn.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    } else {
        if (factBtn) factBtn.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
        if (handBtn) handBtn.className = "px-3 py-1 rounded bg-gray-800 text-emerald-400 cursor-pointer";
    }
    loadAmmoInventory(type);
}

function switchComponentFilter(type) {
    currentComponentFilter = type;
    ['powders', 'primers', 'bullets', 'casings'].forEach(t => {
        const btn = document.getElementById(`comp-btn-${t}`);
        if (!btn) return;
        btn.className = t === type
            ? "px-3 py-1 rounded bg-gray-800 text-emerald-400 cursor-pointer"
            : "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    });
    loadComponentInventory(type);
}

async function loadComponentInventory(type) {
    const container = document.getElementById('components-container');
    if (!container) return;
    container.innerHTML = '<p class="text-gray-400 italic text-sm">Loading...</p>';
    refreshLowStockBanner();
    try {
        const [res, settingsRes] = await Promise.all([
            fetch(`/components/${type}/`),
            fetch('/settings/'),
        ]);
        const items = res.ok ? await res.json() : [];
        const settings = settingsRes.ok ? await settingsRes.json() : {};
        const thresholds = {
            primers: parseFloat(settings.low_stock_primers ?? 200),
            bullets: parseFloat(settings.low_stock_bullets ?? 100),
            casings: parseFloat(settings.low_stock_casings ?? 50),
        };
        const label = {powders:'Powder',primers:'Primer',bullets:'Bullet',casings:'Casing'}[type] || type;
        document.getElementById('inventory-count').innerText = `${items.length} ${label} Item${items.length !== 1 ? 's' : ''}`;
        if (items.length === 0) {
            container.innerHTML = `<p class="text-gray-500 italic text-sm">No ${type} logged yet. Use Add Inventory → Components.</p>`;
            return;
        }
        if (type === 'powders')  container.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(renderPowderCard).join('')}</div>`;
        if (type === 'primers')  container.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(p => renderPrimerCard(p, thresholds.primers)).join('')}</div>`;
        if (type === 'bullets')  renderBulletsGrouped(items, container, thresholds.bullets);
        if (type === 'casings')  container.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(c => renderCasingCard(c, thresholds.casings)).join('')}</div>`;
    } catch(err) {
        container.innerHTML = '<p class="text-red-400 italic text-sm">Failed to load components.</p>';
    }
}

async function refreshLowStockBanner() {
    const banner = document.getElementById('low-stock-banner');
    const list = document.getElementById('low-stock-list');
    if (!banner || !list) return;
    try {
        const res = await fetch('/components/low-stock/');
        const items = res.ok ? await res.json() : [];
        if (items.length === 0) { banner.classList.add('hidden'); return; }
        const colors = { powder: 'bg-emerald-900/60 text-emerald-300 border-emerald-700', primer: 'bg-orange-900/60 text-orange-300 border-orange-700', bullet: 'bg-blue-900/60 text-blue-300 border-blue-700', casing: 'bg-purple-900/60 text-purple-300 border-purple-700' };
        list.innerHTML = items.map(i => `<span class="px-2 py-1 rounded border text-xs font-mono ${colors[i.type] || 'bg-gray-800 text-gray-300 border-gray-600'}">${i.label}: ${i.value}</span>`).join('');
        banner.classList.remove('hidden');
    } catch(_) {}
}

function renderPowderCard(p) {
    return `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3 shadow-lg hover:border-emerald-500/50 transition">
        <div class="flex justify-between items-center">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">POWDER</span>
            <button onclick="deleteComponent('powders',${p.id})" class="text-gray-600 hover:text-red-400 text-xs cursor-pointer">✕</button>
        </div>
        <div>
            <p class="text-base font-bold text-white">${p.brand} ${p.name}</p>
        </div>
        <div class="bg-gray-900/60 rounded-lg p-3 text-center">
            <p class="text-2xl font-bold font-mono text-emerald-400">${p.weight_lbs ?? 0} <span class="text-sm text-gray-400">lbs</span></p>
            <p class="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">On Hand</p>
        </div>
        <div class="border-t border-gray-700 pt-2 space-y-1">
            <p class="text-xs text-gray-400">Cost: <span class="text-white font-mono">$${parseFloat(p.price_paid||0).toFixed(2)}</span></p>
            ${p.notes ? `<p class="text-xs text-gray-500 italic">${p.notes}</p>` : ''}
        </div>
        <div class="flex gap-2">
            <input type="number" step="0.01" placeholder="Update lbs" id="qty-powder-${p.id}"
                class="flex-1 bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none">
            <button onclick="updateComponentQty('powders',${p.id},'weight_lbs')" class="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold rounded cursor-pointer">Save</button>
        </div>
    </div>`;
}

function renderPrimerCard(p, lowThreshold = 200) {
    const low = p.quantity < lowThreshold;
    const qtyColor = low ? 'text-red-400' : 'text-orange-400';
    return `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3 shadow-lg hover:border-orange-500/50 transition">
        <div class="flex justify-between items-center">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-950 text-orange-400 border border-orange-800">PRIMER</span>
            <button onclick="deleteComponent('primers',${p.id})" class="text-gray-600 hover:text-red-400 text-xs cursor-pointer">✕</button>
        </div>
        <div>
            <p class="text-base font-bold text-white">${p.brand}</p>
            <p class="text-sm text-orange-400">${p.primer_type}</p>
        </div>
        <div class="bg-gray-900/60 rounded-lg p-3 text-center">
            <p class="text-2xl font-bold font-mono ${qtyColor}">${(p.quantity??0).toLocaleString()} <span class="text-sm text-gray-400">count</span></p>
            <p class="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">${low ? '⚠️ Low Stock' : 'On Hand'}</p>
        </div>
        <div class="border-t border-gray-700 pt-2 space-y-1">
            <p class="text-xs text-gray-400">Per 1000: <span class="text-white font-mono">$${parseFloat(p.price_paid||0).toFixed(2)}</span></p>
            ${p.notes ? `<p class="text-xs text-gray-500 italic">${p.notes}</p>` : ''}
        </div>
        <div class="flex gap-2">
            <input type="number" placeholder="Update count" id="qty-primer-${p.id}"
                class="flex-1 bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none">
            <button onclick="updateComponentQty('primers',${p.id},'quantity')" class="px-3 py-1.5 bg-orange-700 hover:bg-orange-600 text-white text-xs font-bold rounded cursor-pointer">Save</button>
        </div>
    </div>`;
}

function renderBulletCard(b, lowThreshold = 100) {
    const low = b.quantity < lowThreshold;
    const qtyColor = low ? 'text-red-400' : 'text-blue-400';
    const bcInfo = b.bc_g1 ? `G1: ${b.bc_g1}` : (b.bc_g7 ? `G7: ${b.bc_g7}` : '');
    return `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3 shadow-lg hover:border-blue-500/50 transition">
        <div class="flex justify-between items-center">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800">BULLET</span>
            <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800">${b.weight_gr}gr</span>
                <button onclick="deleteComponent('bullets',${b.id})" class="text-gray-600 hover:text-red-400 text-xs cursor-pointer">✕</button>
            </div>
        </div>
        <div>
            <p class="text-sm font-bold text-white">${b.brand}${b.product_line ? ' · '+b.product_line : ''}</p>
            ${b.bullet_type ? `<p class="text-xs text-gray-400">${b.bullet_type}</p>` : ''}
            ${bcInfo ? `<p class="text-xs text-gray-500 font-mono">BC ${bcInfo}</p>` : ''}
        </div>
        <div class="bg-gray-900/60 rounded-lg p-3 text-center">
            <p class="text-2xl font-bold font-mono ${qtyColor}">${(b.quantity??0).toLocaleString()} <span class="text-sm text-gray-400">count</span></p>
            <p class="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">${low ? '⚠️ Low Stock' : 'On Hand'}</p>
        </div>
        <div class="border-t border-gray-700 pt-2">
            <p class="text-xs text-gray-400">Per box: <span class="text-white font-mono">$${parseFloat(b.price_paid||0).toFixed(2)}</span></p>
            ${b.notes ? `<p class="text-xs text-gray-500 italic">${b.notes}</p>` : ''}
        </div>
        <div class="flex gap-2">
            <input type="number" placeholder="Update count" id="qty-bullet-${b.id}"
                class="flex-1 bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none">
            <button onclick="updateComponentQty('bullets',${b.id},'quantity')" class="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs font-bold rounded cursor-pointer">Save</button>
        </div>
    </div>`;
}

function renderCasingCard(c, lowThreshold = 50) {
    const low = c.quantity < lowThreshold;
    const qtyColor = low ? 'text-red-400' : 'text-purple-400';
    const conditionBadge = c.times_fired === 0
        ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">NEW</span>`
        : `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">${c.times_fired}x FIRED</span>`;
    return `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3 shadow-lg hover:border-purple-500/50 transition">
        <div class="flex justify-between items-center">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950 text-purple-400 border border-purple-800">CASING</span>
            <button onclick="deleteComponent('casings',${c.id})" class="text-gray-600 hover:text-red-400 text-xs cursor-pointer">✕</button>
        </div>
        <div>
            <p class="text-base font-bold text-white">${c.brand}</p>
            <div class="flex items-center gap-2 mt-1">
                <p class="text-sm text-purple-400">${c.caliber}</p>
                ${conditionBadge}
            </div>
        </div>
        <div class="bg-gray-900/60 rounded-lg p-3 text-center">
            <p class="text-2xl font-bold font-mono ${qtyColor}">${(c.quantity??0).toLocaleString()} <span class="text-sm text-gray-400">count</span></p>
            <p class="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">${low ? '⚠️ Low Stock' : 'On Hand'}</p>
        </div>
        <div class="border-t border-gray-700 pt-2 space-y-1">
            <p class="text-xs text-gray-400">Paid: <span class="text-white font-mono">$${parseFloat(c.price_paid||0).toFixed(2)}</span></p>
            ${c.notes ? `<p class="text-xs text-gray-500 italic">${c.notes}</p>` : ''}
        </div>
        <div class="flex gap-2">
            <input type="number" placeholder="Update count" id="qty-casing-${c.id}"
                class="flex-1 bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none">
            <button onclick="updateComponentQty('casings',${c.id},'quantity')" class="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-xs font-bold rounded cursor-pointer">Save</button>
        </div>
    </div>`;
}

function renderBulletsGrouped(bullets, container, lowThreshold = 100) {
    const groups = {};
    bullets.forEach(b => {
        const cal = b.caliber || 'Unknown';
        if (!groups[cal]) groups[cal] = [];
        groups[cal].push(b);
    });
    container.innerHTML = Object.entries(groups).sort(([a],[b]) => a.localeCompare(b)).map(([cal, items]) => `
        <div class="mb-8">
            <div class="flex items-center gap-3 mb-3">
                <span class="text-xs font-bold uppercase tracking-wider text-amber-500 font-mono">${cal}</span>
                <span class="text-[10px] text-gray-500">${items.length} variant${items.length !== 1 ? 's' : ''}</span>
                <div class="flex-1 border-t border-gray-700/60"></div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                ${items.map(b => renderBulletCard(b, lowThreshold)).join('')}
            </div>
        </div>`
    ).join('');
}

async function updateComponentQty(type, id, field) {
    const inputId = `qty-${type.slice(0,-1)}-${id}`;
    const input = document.getElementById(inputId);
    if (!input || input.value === '') return;
    const val = field === 'quantity' ? parseInt(input.value) : parseFloat(input.value);
    try {
        const res = await fetch(`/components/${type}/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [field]: val })
        });
        if (res.ok) { showToast('Updated.'); loadComponentInventory(type); }
        else showToast('Update failed.', 'error');
    } catch(_) { showToast('Error updating.', 'error'); }
}

async function deleteComponent(type, id) {
    if (!confirm('Delete this component record?')) return;
    try {
        const res = await fetch(`/components/${type}/${id}`, { method: 'DELETE' });
        if (res.ok) { showToast('Deleted.'); loadComponentInventory(type); }
        else showToast('Delete failed.', 'error');
    } catch(_) { showToast('Error deleting.', 'error'); }
}

async function loadScopes() {
    const container = document.getElementById('scopes-container');
    if (!container) return;
    container.innerHTML = '<p class="text-gray-400 col-span-3 italic text-sm">Loading optics...</p>';

    try {
        const res = await fetch('/scopes/');
        const scopes = res.ok ? await res.json() : [];
        document.getElementById('inventory-count').innerText = `${scopes.length} Optic${scopes.length !== 1 ? 's' : ''} Registered`;

        if (scopes.length === 0) {
            container.innerHTML = '<p class="text-gray-500 col-span-3 italic text-sm">No optics registered. Add one via the Add Inventory form.</p>';
            return;
        }
        container.innerHTML = scopes.map(renderScopeCard).join('');
    } catch(err) {
        container.innerHTML = '<p class="text-red-400 col-span-3 italic text-sm">Failed to load optics.</p>';
    }
}

function renderScopeCard(s) {
    const imgHtml = s.image_path
        ? `<img src="${s.image_path}" class="w-full h-full object-cover">`
        : `<div class="w-full h-full flex items-center justify-center text-5xl">🔭</div>`;
    const mountLabel = s.mounted_on
        ? `<span class="text-emerald-400 font-medium">${s.mounted_on}</span>`
        : `<span class="text-gray-500 italic">Unmounted</span>`;
    const mountBtnLabel = s.mounted_on ? '🔄 Change Mount' : '📍 Mount Scope';

    return `
    <div id="scope-card-${s.id}"
        data-mount-type="${s.mount_type || ''}"
        data-mount-id="${s.mount_type === 'firearm' ? (s.mounted_firearm_id || '') : (s.mounted_barrel_id || '')}"
        class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-xl">
        <div class="w-full h-40 bg-gray-950 overflow-hidden">${imgHtml}</div>
        <div class="p-4 space-y-2">
            <div class="flex justify-between items-center">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800">OPTIC</span>
                <span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-gray-900 text-gray-300 border border-gray-700">${s.units || 'MOA'}</span>
            </div>
            <div>
                <h3 class="text-base font-bold text-white">${s.brand || '—'}</h3>
                <p class="text-sm text-amber-500">${s.model || '—'}</p>
            </div>
            <div class="border-t border-gray-700 pt-2 space-y-1">
                <p class="text-xs text-gray-400">📍 ${mountLabel}</p>
                <p class="text-xs text-gray-400">Cost: <span class="text-white font-mono">$${parseFloat(s.price_paid || 0).toFixed(2)}</span></p>
            </div>
            <!-- Mount editor (hidden until user clicks) -->
            <div id="scope-editor-${s.id}" class="hidden border-t border-gray-600 pt-3 space-y-2">
                <div class="flex gap-2 items-center flex-wrap">
                    <select id="scope-installed-${s.id}" onchange="toggleScopeMountSelect(${s.id})"
                        class="bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none">
                        <option value="yes" ${s.mount_type ? 'selected' : ''}>Installed</option>
                        <option value="no" ${!s.mount_type ? 'selected' : ''}>Unmounted</option>
                    </select>
                    <select id="scope-mount-select-${s.id}"
                        class="flex-1 min-w-0 bg-gray-700 border border-gray-600 rounded p-1.5 text-xs text-white focus:outline-none ${!s.mount_type ? 'hidden' : ''}">
                        <option value="">Loading…</option>
                    </select>
                </div>
                <div class="flex gap-2">
                    <button onclick="saveScopeMount(${s.id})" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-1.5 rounded transition cursor-pointer">Save</button>
                    <button onclick="closeScopeMountEditor(${s.id})" class="px-3 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold py-1.5 rounded transition cursor-pointer">Cancel</button>
                </div>
            </div>
            <button onclick="openScopeMountEditor(${s.id})"
                class="w-full mt-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold rounded transition cursor-pointer">
                ${mountBtnLabel}
            </button>
        </div>
    </div>`;
}

async function openScopeMountEditor(scopeId) {
    const editor = document.getElementById(`scope-editor-${scopeId}`);
    const select = document.getElementById(`scope-mount-select-${scopeId}`);
    const installedSel = document.getElementById(`scope-installed-${scopeId}`);
    if (!editor || !select) return;

    editor.classList.remove('hidden');

    // Fetch available mounts
    try {
        const res = await fetch(`/available-mounts/?for_scope_id=${scopeId}`);
        if (!res.ok) return;
        const data = await res.json();

        let opts = `<option value="">-- Select Platform --</option>`;
        if (data.firearms.length > 0) {
            opts += `<optgroup label="── Rifles ──">` +
                data.firearms.map(f => `<option value="firearm:${f.id}">${f.label}</option>`).join('') +
                `</optgroup>`;
        }
        if (data.tc_barrels.length > 0) {
            opts += `<optgroup label="── TC Barrels ──">` +
                data.tc_barrels.map(b => `<option value="barrel:${b.id}">${b.label}</option>`).join('') +
                `</optgroup>`;
        }
        select.innerHTML = opts;

        // Pre-select current mount
        const card = document.getElementById(`scope-card-${scopeId}`);
        if (card) {
            const mountType = installedSel.value === 'yes' ? card.dataset.mountType : null;
            const mountId   = card.dataset.mountId;
            if (mountType && mountId) {
                const val = `${mountType}:${mountId}`;
                for (const opt of select.options) {
                    if (opt.value === val) { opt.selected = true; break; }
                }
            }
        }
    } catch(_) {}
}

function toggleScopeMountSelect(scopeId) {
    const sel = document.getElementById(`scope-installed-${scopeId}`);
    const mountSel = document.getElementById(`scope-mount-select-${scopeId}`);
    if (!sel || !mountSel) return;
    if (sel.value === 'yes') {
        mountSel.classList.remove('hidden');
    } else {
        mountSel.classList.add('hidden');
    }
}

async function saveScopeMount(scopeId) {
    const installedSel = document.getElementById(`scope-installed-${scopeId}`);
    const mountSel     = document.getElementById(`scope-mount-select-${scopeId}`);
    if (!installedSel) return;

    let mount_type = null;
    let mount_id   = null;

    if (installedSel.value === 'yes' && mountSel && mountSel.value) {
        const [type, id] = mountSel.value.split(':');
        mount_type = type;
        mount_id   = parseInt(id);
    }

    try {
        const res = await fetch(`/scopes/${scopeId}/mount`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mount_type, mount_id })
        });
        if (res.ok) {
            showToast('Scope mount updated.');
            loadScopes();
        } else {
            showToast('Failed to update mount.', 'error');
        }
    } catch(_) { showToast('Error saving mount.', 'error'); }
}

function closeScopeMountEditor(scopeId) {
    document.getElementById(`scope-editor-${scopeId}`)?.classList.add('hidden');
}

async function loadAmmoInventory(type) {
    const container = document.getElementById('ammo-container');
    if (!container) return;
    container.innerHTML = '<p class="text-gray-400 italic text-sm">Loading ammunition...</p>';

    try {
        const res = await fetch('/ammo/');
        const all = res.ok ? await res.json() : [];
        const filtered = all.filter(a => type === 'handload' ? a.is_handload : !a.is_handload);

        document.getElementById('inventory-count').innerText = `${filtered.length} Load${filtered.length !== 1 ? 's' : ''} Registered`;

        if (filtered.length === 0) {
            container.innerHTML = `<p class="text-gray-500 italic text-sm">No ${type === 'handload' ? 'handload recipes' : 'factory loads'} registered.</p>`;
            return;
        }

        // Group by caliber
        const groups = {};
        filtered.forEach(a => {
            const cal = a.caliber || 'Unknown Caliber';
            if (!groups[cal]) groups[cal] = [];
            groups[cal].push(a);
        });

        container.innerHTML = Object.entries(groups).sort(([a],[b]) => a.localeCompare(b)).map(([cal, loads]) => `
            <div class="mb-8">
                <div class="flex items-center gap-3 mb-3">
                    <span class="text-xs font-bold uppercase tracking-wider text-amber-500 font-mono">${cal}</span>
                    <span class="text-[10px] text-gray-500">${loads.length} load${loads.length !== 1 ? 's' : ''}</span>
                    <div class="flex-1 border-t border-gray-700/60"></div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    ${loads.map(renderAmmoCard).join('')}
                </div>
            </div>`
        ).join('');
    } catch(err) {
        container.innerHTML = '<p class="text-red-400 italic text-sm">Failed to load ammunition.</p>';
    }
}

function renderAmmoCard(ammo) {
    const isHandload = ammo.is_handload;
    const badgeCls = isHandload
        ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
        : 'bg-blue-950 text-blue-400 border-blue-800';
    const badgeLabel = isHandload ? 'HANDLOAD' : 'FACTORY';
    const line = ammo.line_or_powder || '';

    let detail = '';
    if (isHandload) {
        if (line)              detail += `<p class="text-[11px] text-gray-400">Powder: <span class="text-gray-200">${line}</span></p>`;
        if (ammo.charge_weight) detail += `<p class="text-[11px] text-gray-400">Charge: <span class="text-gray-200 font-mono">${ammo.charge_weight}gr</span></p>`;
        if (ammo.coal)         detail += `<p class="text-[11px] text-gray-400">COAL: <span class="text-gray-200 font-mono">${ammo.coal}&quot;</span></p>`;
    } else {
        if (line) detail += `<p class="text-[11px] text-gray-400">Line: <span class="text-gray-200">${line}</span></p>`;
    }

    return `
    <div onclick="window.location.href='ammo-detail.html?id=${ammo.id}'"
         class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-2 hover:border-amber-500/60 transition cursor-pointer shadow-lg">
        <div class="flex justify-between items-start">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeCls}">${badgeLabel}</span>
            <span class="text-xs font-mono font-bold text-amber-400">${ammo.bullet_weight}gr</span>
        </div>
        <div>
            <h3 class="text-sm font-bold text-white leading-tight">${ammo.brand || '—'}</h3>
            <p class="text-[11px] text-gray-400">${ammo.bullet_type || '—'}</p>
        </div>
        ${detail ? `<div class="border-t border-gray-700/60 pt-2 space-y-0.5">${detail}</div>` : ''}
    </div>`;
}

function switchFormCategory(targetCat) {
    const panes = { 'cat-platforms': 'pane-platforms', 'cat-ammunition': 'pane-ammunition', 'cat-components': 'pane-components' };
    const btns  = { 'cat-platforms': 'btn-cat-platforms', 'cat-ammunition': 'btn-cat-ammunition', 'cat-components': 'btn-cat-components' };
    Object.entries(panes).forEach(([cat, paneId]) => {
        const pane = document.getElementById(paneId);
        const btn  = document.getElementById(btns[cat]);
        if (cat === targetCat) {
            pane?.classList.remove('hidden');
            if (btn) btn.className = "px-4 py-1.5 text-xs font-bold rounded bg-amber-600 text-white cursor-pointer";
        } else {
            pane?.classList.add('hidden');
            if (btn) btn.className = "px-4 py-1.5 text-xs font-bold rounded text-gray-400 hover:text-gray-200 cursor-pointer";
        }
    });
}

function toggleAmmoType(type) {
    document.querySelectorAll('.ammo-variant-form').forEach(form => form.classList.add('hidden'));
    const factForm = document.getElementById('ammo-factory-form');
    const handForm = document.getElementById('ammo-handload-form');
    const btnFact = document.getElementById('btn-ammo-factory');
    const btnHand = document.getElementById('btn-ammo-handloads');

    if (type === 'factory') {
        if (factForm) factForm.classList.remove('hidden');
        if (btnFact) btnFact.className = "px-3 py-1 text-xs font-bold rounded bg-blue-600 text-white cursor-pointer";
        if (btnHand) btnHand.className = "px-3 py-1 text-xs font-bold rounded text-gray-400 bg-gray-950 hover:text-white cursor-pointer";
    } else {
        if (handForm) handForm.classList.remove('hidden');
        if (btnFact) btnFact.className = "px-3 py-1 text-xs font-bold rounded text-gray-400 bg-gray-950 hover:text-white cursor-pointer";
        if (btnHand) btnHand.className = "px-3 py-1 text-xs font-bold rounded bg-emerald-600 text-white cursor-pointer";
    }
}

// ── Threshold Settings Panel ───────────────────────────────────────────────────

async function toggleThresholdSettings() {
    const panel = document.getElementById('threshold-panel');
    const icon  = document.getElementById('threshold-toggle-icon');
    const isHidden = panel.classList.contains('hidden');
    panel.classList.toggle('hidden');
    icon.textContent = isHidden ? '▼' : '▶';
    if (isHidden) await loadThresholds();
}

async function loadThresholds() {
    try {
        const res = await fetch('/settings/');
        if (!res.ok) return;
        const s = await res.json();
        const f = v => document.getElementById(v);
        if (f('thresh-powder'))  f('thresh-powder').value  = s.low_stock_powder_lbs ?? 0.5;
        if (f('thresh-primers')) f('thresh-primers').value = s.low_stock_primers    ?? 200;
        if (f('thresh-bullets')) f('thresh-bullets').value = s.low_stock_bullets    ?? 100;
        if (f('thresh-casings')) f('thresh-casings').value = s.low_stock_casings    ?? 50;
    } catch(_) {}
}

async function saveThresholds() {
    const payload = {
        low_stock_powder_lbs: document.getElementById('thresh-powder')?.value  || '0.5',
        low_stock_primers:    document.getElementById('thresh-primers')?.value || '200',
        low_stock_bullets:    document.getElementById('thresh-bullets')?.value || '100',
        low_stock_casings:    document.getElementById('thresh-casings')?.value || '50',
    };
    try {
        const res = await fetch('/settings/', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) { showToast('Alert thresholds saved.'); refreshLowStockBanner(); }
        else showToast('Failed to save thresholds.', 'error');
    } catch(_) { showToast('Error saving thresholds.', 'error'); }
}

async function setupMeasureDropdowns() {
    const gunSelect = document.getElementById('select-gun');
    const ammoSelect = document.getElementById('select-ammo');
    if (!gunSelect || !ammoSelect) return;

    const dateInput = document.getElementById('session-date');
    if (dateInput && !dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }
    try {
        const [gunsRes, tcRes, ammoRes] = await Promise.all([
            fetch('/catalog/'), fetch('/tc-barrels/'), fetch('/ammo/')
        ]);
        const items    = gunsRes.ok ? await gunsRes.json() : [];
        const tcBarrels = tcRes.ok  ? await tcRes.json()   : [];
        const ammoItems = ammoRes.ok ? await ammoRes.json() : [];

        let gunOptions = `<option value="">-- Select Platform --</option>`;
        if (items.length > 0) {
            gunOptions += `<optgroup label="── Rifles ──">` +
                items.map(g => `<option value="${g.id}">${g.brand} ${g.model}</option>`).join('') +
                `</optgroup>`;
        }
        if (tcBarrels.length > 0) {
            gunOptions += `<optgroup label="── Thompson Center Barrels ──">` +
                tcBarrels.map(b => `<option value="${b.id}" data-type="tc">${b.tc_platform} ${b.caliber}</option>`).join('') +
                `</optgroup>`;
        }
        gunSelect.innerHTML = gunOptions;

        if (ammoItems.length > 0) {
            ammoSelect.innerHTML = `<option value="">-- Select Load Profile --</option>` +
                ammoItems.map(a => `<option value="${a.id}">${a.brand} (${a.bullet_weight}gr)</option>`).join('');
        }
    } catch(e) {}
}

const targetUpload = document.getElementById('target-upload');
if (targetUpload) {
    targetUpload.addEventListener('change', function(e) {
        const file = e.target.files[0]; if (!file) return;
        const reader = new FileReader();
        reader.onload = function(event) {
            imgElement.onload = function() {
                canvas.width = imgElement.naturalWidth; canvas.height = imgElement.naturalHeight;
                state = "calibrating"; calibrationPoints = []; currentGroupShots = []; groups = []; pixelsPerInch = null; resetDragState();
                
                const banner = document.getElementById('status-banner');
                const calBox = document.getElementById('calibration-box');
                const envBox = document.getElementById('session-environment');
                const metaBox = document.getElementById('group-metadata');
                const liveRes = document.getElementById('live-result');
                const dlBtn = document.getElementById('download-btn');
                const saveBtn = document.getElementById('db-save-session-btn');
                
                if (banner) {
                    banner.classList.remove('hidden');
                    banner.innerText = "Step 1: Click TWO points on target grid matching reference scale line intersection.";
                }
                if (calBox) calBox.classList.add('hidden');
                if (envBox) envBox.classList.remove('hidden');
                if (metaBox) metaBox.classList.add('hidden');
                if (liveRes) liveRes.classList.add('hidden');
                if (dlBtn) dlBtn.classList.add('hidden');
                if (saveBtn) saveBtn.classList.add('hidden');
                
                updateSidebarList(); redrawCanvas();
            };
            imgElement.src = event.target.result;
        };
        reader.readAsDataURL(file);
    });
}

function resetDragState() { liveBoxPos = { x: 0, y: 0, customized: false }; isDraggingBox = false; isDraggingLabelIdx = null; }
function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width; const scaleY = canvas.height / rect.height;
    let clientX, clientY;
    if (e.touches && e.touches.length > 0) {
        clientX = e.touches[0].clientX; clientY = e.touches[0].clientY;
    } else if (e.changedTouches && e.changedTouches.length > 0) {
        // touchend has an empty e.touches; use changedTouches for the released finger position
        clientX = e.changedTouches[0].clientX; clientY = e.changedTouches[0].clientY;
    } else {
        clientX = e.clientX; clientY = e.clientY;
    }
    return { x: (clientX - rect.left) * scaleX, y: (clientY - rect.top) * scaleY };
}

if (canvas) {
    canvas.addEventListener('mousedown', handleStart);
    canvas.addEventListener('touchstart', handleStart, { passive: false });
    canvas.addEventListener('mousemove', handleMove);
    canvas.addEventListener('touchmove', handleMove, { passive: false });
    canvas.addEventListener('mouseup', handleEnd);
    canvas.addEventListener('touchend', handleEnd);
}

function handleStart(e) {
    if (state === "idle") return;
    if (e.touches && e.touches.length > 1) { isMultiTouch = true; return; }
    if (e.touches) {
        // New touch gesture starting — clear the flag so touch path runs fresh.
        touchHandled = false;
    } else if (touchHandled) {
        // Synthetic mousedown fired by the browser after touchend — skip it.
        return;
    }
    isMultiTouch = false;
    touchStartClientPos = e.touches ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null;
    const coords = getCanvasCoords(e);
    if (state === "measuring") {
        if (coords.x >= liveBoxPos.x && coords.x <= liveBoxPos.x + liveBoxDims.w && coords.y >= liveBoxPos.y && coords.y <= liveBoxPos.y + liveBoxDims.h) {
            isDraggingBox = true; dragOffset.x = coords.x - liveBoxPos.x; dragOffset.y = coords.y - liveBoxPos.y; return;
        }
    }
}
function handleMove(e) {
    if (state === "idle") return;
    if (e.touches && e.touches.length > 1) { isMultiTouch = true; }
    const coords = getCanvasCoords(e);
    if (isDraggingBox) { e.preventDefault(); liveBoxPos.x = coords.x - dragOffset.x; liveBoxPos.y = coords.y - dragOffset.y; liveBoxPos.customized = true; redrawCanvas(); }
}
function handleEnd(e) {
    if (state === "idle") return;
    if (e.changedTouches) {
        // touchend: mark that touch is handling this gesture so the synthetic mouseup is ignored.
        touchHandled = true;
    } else if (touchHandled) {
        // Synthetic mouseup fired by the browser after touchend — skip it.
        touchHandled = false;
        return;
    }
    const wasMultiTouch = isMultiTouch;
    if (e.touches && e.touches.length === 0) { isMultiTouch = false; }
    if (wasMultiTouch) { isDraggingBox = false; touchStartClientPos = null; return; }
    if (isDraggingBox) { isDraggingBox = false; return; }
    if (touchStartClientPos && e.changedTouches) {
        const dx = e.changedTouches[0].clientX - touchStartClientPos.x;
        const dy = e.changedTouches[0].clientY - touchStartClientPos.y;
        touchStartClientPos = null;
        if (Math.sqrt(dx * dx + dy * dy) > 10) return;
    }
    touchStartClientPos = null;
    const coords = getCanvasCoords(e);
    if (state === "calibrating") {
        if (calibrationPoints.length < 2) calibrationPoints.push({ x: coords.x, y: coords.y });
        redrawCanvas();
        if (calibrationPoints.length === 2) {
            const calBox = document.getElementById('calibration-box');
            const banner = document.getElementById('status-banner');
            if (calBox) calBox.classList.remove('hidden');
            if (banner) banner.innerText = "Input exact physical scale dimension width (Inches) and click Lock Calibration.";
        }
    } else if (state === "measuring") {
        const sNum = currentGroupShots.length + 1;
        const vIn = prompt(`Enter Velocity (fps) for Shot #${sNum} (Optional):`);
        let velocity = vIn && !isNaN(parseFloat(vIn)) ? parseFloat(vIn) : null;
        currentGroupShots.push({ x: coords.x, y: coords.y, velocity: velocity });
        if (currentGroupShots.length >= 2) updateLiveResults();
        redrawCanvas();
    }
}

function lockCalibration() {
    const refInches = document.getElementById('ref-inches');
    if (!refInches) return;
    const inches = parseFloat(refInches.value);
    if (calibrationPoints.length < 2 || isNaN(inches) || inches <= 0) return;
    pixelsPerInch = Math.sqrt(Math.pow(calibrationPoints[1].x - calibrationPoints[0].x, 2) + Math.pow(calibrationPoints[1].y - calibrationPoints[0].y, 2)) / inches;
    state = "measuring";
    
    const calBox = document.getElementById('calibration-box');
    const metaBox = document.getElementById('group-metadata');
    if (calBox) calBox.classList.add('hidden');
    if (metaBox) metaBox.classList.remove('hidden');
}

function resetCalibration() {
    calibrationPoints = [];
    pixelsPerInch = null;
    currentGroupShots = [];
    state = "calibrating";
    const calBox = document.getElementById('calibration-box');
    const metaBox = document.getElementById('group-metadata');
    const banner = document.getElementById('status-banner');
    const liveRes = document.getElementById('live-result');
    if (calBox) calBox.classList.add('hidden');
    if (metaBox) metaBox.classList.add('hidden');
    if (liveRes) liveRes.classList.add('hidden');
    if (banner) banner.innerText = "Step 1: Click TWO points on target grid matching reference scale line intersection.";
    redrawCanvas();
}

function updateLiveResults() {
    if (currentGroupShots.length < 2 || !pixelsPerInch) return;
    const liveRes = document.getElementById('live-result');
    if (liveRes) {
        liveRes.classList.remove('hidden');
        liveRes.innerText = `Current Span: ${(findMaxDistance(currentGroupShots) / pixelsPerInch).toFixed(3)}"`;
    }
}

function findMaxDistance(pts) {
    let maxDist = 0;
    for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
            const d = Math.sqrt(Math.pow(pts[j].x - pts[i].x, 2) + Math.pow(pts[j].y - pts[i].y, 2));
            if (d > maxDist) maxDist = d;
        }
    }
    return maxDist;
}

function saveCurrentGroup() {
    if (currentGroupShots.length < 2) {
        showToast("Need at least 2 shots to save a group.", "error");
        return;
    }
    const gunSelect = document.getElementById('select-gun');
    const ammoSelect = document.getElementById('select-ammo');
    if (!gunSelect || !gunSelect.value) {
        showToast("Please select a Firearm before saving.", "error");
        return;
    }
    if (!ammoSelect || !ammoSelect.value) {
        showToast("Please select a Load Profile before saving.", "error");
        return;
    }

    const size = (findMaxDistance(currentGroupShots) / pixelsPerInch).toFixed(3);
    const groupData = {
        shots: [...currentGroupShots],
        size,
        gunText: gunSelect.options[gunSelect.selectedIndex].text,
        ammoText: ammoSelect.options[ammoSelect.selectedIndex].text,
        boxX: liveBoxPos.x,
        boxY: liveBoxPos.y,
        chrono: null,
        dateText: "",
        tempText: "",
        cropRect: null
    };

    if (imgElement.src && imgElement.naturalWidth > 0) {
        openCropModal(groupData);
    } else {
        commitGroupToList(groupData);
    }
}

function commitGroupToList(groupData) {
    groups.push(groupData);
    currentGroupShots = [];
    const liveRes = document.getElementById('live-result');
    if (liveRes) liveRes.classList.add('hidden');
    resetDragState();
    updateSidebarList();
    redrawCanvas();
    showToast(`Group ${groups.length} saved — ${groupData.size}"`);
}

function openCropModal(groupData) {
    pendingGroupData = groupData;
    const cropCanvas = document.getElementById('crop-canvas');

    const MAX_W = 820, MAX_H = 520;
    cropDisplayScale = Math.min(MAX_W / canvas.width, MAX_H / canvas.height, 1);
    cropCanvas.width = Math.round(canvas.width * cropDisplayScale);
    cropCanvas.height = Math.round(canvas.height * cropDisplayScale);

    // Pre-select a crop region around the shot bounding box + padding
    const shots = groupData.shots;
    const PAD = 200;
    const minX = Math.max(0, Math.min(...shots.map(s => s.x)) - PAD);
    const minY = Math.max(0, Math.min(...shots.map(s => s.y)) - PAD);
    const maxX = Math.min(canvas.width,  Math.max(...shots.map(s => s.x)) + PAD);
    const maxY = Math.min(canvas.height, Math.max(...shots.map(s => s.y)) + PAD);
    cropRect = { x: minX, y: minY, w: maxX - minX, h: maxY - minY };

    drawCropOverlay();
    document.getElementById('crop-modal').classList.remove('hidden');

    cropCanvas.onmousedown  = cropHandleStart;
    cropCanvas.onmousemove  = cropHandleMove;
    cropCanvas.onmouseup    = cropHandleEnd;
    cropCanvas.onmouseleave = cropHandleEnd;
    cropCanvas.ontouchstart = (e) => { e.preventDefault(); cropHandleStart(e.touches[0]); };
    cropCanvas.ontouchmove  = (e) => { e.preventDefault(); cropHandleMove(e.touches[0]); };
    cropCanvas.ontouchend   = cropHandleEnd;
}

function drawCropOverlay() {
    const cropCanvas = document.getElementById('crop-canvas');
    const cropCtx = cropCanvas.getContext('2d');
    const s = cropDisplayScale;

    cropCtx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
    cropCtx.drawImage(imgElement, 0, 0, cropCanvas.width, cropCanvas.height);

    // Shot dots for reference
    if (pendingGroupData) {
        pendingGroupData.shots.forEach((p, i) => {
            pendingGroupData.shots.forEach((q, j) => {
                if (j <= i) return;
                cropCtx.strokeStyle = '#ef4444';
                cropCtx.lineWidth = Math.max(2, 4 * s);
                cropCtx.beginPath();
                cropCtx.moveTo(p.x * s, p.y * s);
                cropCtx.lineTo(q.x * s, q.y * s);
                cropCtx.stroke();
            });
            cropCtx.fillStyle = '#ef4444';
            cropCtx.beginPath();
            cropCtx.arc(p.x * s, p.y * s, Math.max(4, 7 * s), 0, Math.PI * 2);
            cropCtx.fill();
        });
    }

    const rx = cropRect.x * s, ry = cropRect.y * s;
    const rw = cropRect.w * s, rh = cropRect.h * s;

    // Dark vignette outside crop region
    cropCtx.fillStyle = 'rgba(0,0,0,0.62)';
    cropCtx.fillRect(0, 0, cropCanvas.width, ry);
    cropCtx.fillRect(0, ry + rh, cropCanvas.width, cropCanvas.height - ry - rh);
    cropCtx.fillRect(0, ry, rx, rh);
    cropCtx.fillRect(rx + rw, ry, cropCanvas.width - rx - rw, rh);

    // Crop border
    cropCtx.strokeStyle = '#f59e0b';
    cropCtx.lineWidth = 2;
    cropCtx.strokeRect(rx, ry, rw, rh);

    // Rule-of-thirds grid
    cropCtx.strokeStyle = 'rgba(255,255,255,0.18)';
    cropCtx.lineWidth = 0.5;
    cropCtx.beginPath();
    cropCtx.moveTo(rx + rw/3, ry);    cropCtx.lineTo(rx + rw/3, ry + rh);
    cropCtx.moveTo(rx + 2*rw/3, ry); cropCtx.lineTo(rx + 2*rw/3, ry + rh);
    cropCtx.moveTo(rx, ry + rh/3);   cropCtx.lineTo(rx + rw, ry + rh/3);
    cropCtx.moveTo(rx, ry + 2*rh/3); cropCtx.lineTo(rx + rw, ry + 2*rh/3);
    cropCtx.stroke();

    // Corner handles
    const HS = 9;
    cropCtx.fillStyle = '#f59e0b';
    [[rx, ry], [rx + rw, ry], [rx, ry + rh], [rx + rw, ry + rh]].forEach(([hx, hy]) => {
        cropCtx.fillRect(hx - HS/2, hy - HS/2, HS, HS);
    });
}

function getCropCanvasPos(e) {
    const cropCanvas = document.getElementById('crop-canvas');
    const rect = cropCanvas.getBoundingClientRect();
    const sx = cropCanvas.width / rect.width;
    const sy = cropCanvas.height / rect.height;
    return { x: (e.clientX - rect.left) * sx, y: (e.clientY - rect.top) * sy };
}

function getCropHitMode(dx, dy) {
    const s = cropDisplayScale;
    const rx = cropRect.x * s, ry = cropRect.y * s;
    const rw = cropRect.w * s, rh = cropRect.h * s;
    const HIT = 12;
    if (Math.abs(dx - rx) <= HIT && Math.abs(dy - ry) <= HIT)           return 'nw';
    if (Math.abs(dx - (rx+rw)) <= HIT && Math.abs(dy - ry) <= HIT)      return 'ne';
    if (Math.abs(dx - rx) <= HIT && Math.abs(dy - (ry+rh)) <= HIT)      return 'sw';
    if (Math.abs(dx - (rx+rw)) <= HIT && Math.abs(dy - (ry+rh)) <= HIT) return 'se';
    if (dx >= rx && dx <= rx+rw && dy >= ry && dy <= ry+rh)              return 'move';
    return 'draw';
}

function cropHandleStart(e) {
    const { x: dx, y: dy } = getCropCanvasPos(e);
    cropDragState = { active: true, mode: getCropHitMode(dx, dy), startX: dx, startY: dy, origRect: { ...cropRect } };
}

function cropHandleMove(e) {
    if (!cropDragState.active) return;
    const { x: dx, y: dy } = getCropCanvasPos(e);
    const s = cropDisplayScale;
    const W = canvas.width, H = canvas.height;
    const orig = cropDragState.origRect;
    const dxC = (dx - cropDragState.startX) / s;
    const dyC = (dy - cropDragState.startY) / s;

    if (cropDragState.mode === 'move') {
        cropRect.x = Math.max(0, Math.min(W - orig.w, orig.x + dxC));
        cropRect.y = Math.max(0, Math.min(H - orig.h, orig.y + dyC));
    } else if (cropDragState.mode === 'draw') {
        const cx = dx / s, cy = dy / s;
        const sx = cropDragState.startX / s, sy = cropDragState.startY / s;
        cropRect.x = Math.max(0, Math.min(cx, sx));
        cropRect.y = Math.max(0, Math.min(cy, sy));
        cropRect.w = Math.min(Math.abs(cx - sx), W - cropRect.x);
        cropRect.h = Math.min(Math.abs(cy - sy), H - cropRect.y);
    } else {
        let nx = orig.x, ny = orig.y, nw = orig.w, nh = orig.h;
        if (cropDragState.mode === 'nw') { nx = orig.x + dxC; ny = orig.y + dyC; nw = orig.w - dxC; nh = orig.h - dyC; }
        if (cropDragState.mode === 'ne') { ny = orig.y + dyC; nw = orig.w + dxC; nh = orig.h - dyC; }
        if (cropDragState.mode === 'sw') { nx = orig.x + dxC; nw = orig.w - dxC; nh = orig.h + dyC; }
        if (cropDragState.mode === 'se') { nw = orig.w + dxC; nh = orig.h + dyC; }
        if (nw > 30 && nh > 30) {
            cropRect.x = Math.max(0, nx); cropRect.y = Math.max(0, ny);
            cropRect.w = Math.min(nw, W - cropRect.x); cropRect.h = Math.min(nh, H - cropRect.y);
        }
    }
    drawCropOverlay();
}

function cropHandleEnd() { cropDragState.active = false; }

function cropConfirm() {
    if (pendingGroupData) {
        pendingGroupData.cropRect = cropRect.w > 0 && cropRect.h > 0 ? { ...cropRect } : null;
        commitGroupToList(pendingGroupData);
        pendingGroupData = null;
    }
    closeCropModal();
}

function cropSaveFullImage() {
    if (pendingGroupData) {
        pendingGroupData.cropRect = null;
        commitGroupToList(pendingGroupData);
        pendingGroupData = null;
    }
    closeCropModal();
}

function closeCropModal() {
    document.getElementById('crop-modal').classList.add('hidden');
    const cropCanvas = document.getElementById('crop-canvas');
    cropCanvas.onmousedown = cropCanvas.onmousemove = cropCanvas.onmouseup = cropCanvas.onmouseleave = null;
    cropCanvas.ontouchstart = cropCanvas.ontouchmove = cropCanvas.ontouchend = null;
}

function redrawCanvas() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (imgElement.src) ctx.drawImage(imgElement, 0, 0);

    // Draw saved groups with their overlay boxes
    groups.forEach(g => {
        drawConnections(g.shots, '#ef4444', 6);
        drawStatsBox(g.shots, g.size, g.boxX, g.boxY, g.ammoText, g.gunText);
    });

    // Draw current in-progress shots
    if (currentGroupShots.length > 0) {
        drawConnections(currentGroupShots, '#3b82f6', 6);
        if (currentGroupShots.length >= 2 && pixelsPerInch) {
            const size = (findMaxDistance(currentGroupShots) / pixelsPerInch).toFixed(3);
            const gunSel  = document.getElementById('select-gun');
            const ammoSel = document.getElementById('select-ammo');
            const livePlatform = gunSel?.selectedIndex  > 0 ? gunSel.options[gunSel.selectedIndex].text   : '';
            const liveLoad     = ammoSel?.selectedIndex > 0 ? ammoSel.options[ammoSel.selectedIndex].text : '';
            drawStatsBox(currentGroupShots, size, liveBoxPos.x, liveBoxPos.y, liveLoad, livePlatform);
        }
    }

    // Draw calibration points as blue dots with a line between them
    if (calibrationPoints.length > 0) {
        const s = canvasScale();
        ctx.fillStyle = '#3b82f6';
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 3 * s;
        calibrationPoints.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 10 * s, 0, Math.PI * 2);
            ctx.fill();
        });
        if (calibrationPoints.length === 2) {
            ctx.beginPath();
            ctx.setLineDash([10 * s, 6 * s]);
            ctx.moveTo(calibrationPoints[0].x, calibrationPoints[0].y);
            ctx.lineTo(calibrationPoints[1].x, calibrationPoints[1].y);
            ctx.stroke();
            ctx.setLineDash([]);
        }
    }
}

function drawStatsBox(shots, sizeInches, boxX, boxY, loadLabel, platformLabel) {
    if (!shots || shots.length < 2) return;

    const velocities = shots.map(s => s.velocity).filter(v => v !== null);
    const hasChrono = velocities.length > 0;

    const trunc = (s, n) => s && s.length > n ? s.slice(0, n - 1) + '…' : (s || '');
    const loadStr = trunc(loadLabel, 34);
    const platStr = trunc(platformLabel, 34);

    const s = canvasScale();
    const fs = (n) => `${Math.round(n * s)}px`;

    // Build lines: [text, font, color, lineAdvance]
    const lines = [
        [`GROUP: ${sizeInches}"`, `bold ${fs(24)} monospace`, '#f59e0b', 32 * s],
    ];
    if (loadStr) lines.push([loadStr, `bold ${fs(17)} monospace`, '#a3e635', 23 * s]);
    if (platStr) lines.push([platStr, `${fs(16)} monospace`,      '#60a5fa', 22 * s]);
    lines.push([`${shots.length} shots`, `${fs(17)} monospace`, '#9ca3af', 23 * s]);

    if (hasChrono) {
        const avg = Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length);
        const es  = Math.max(...velocities) - Math.min(...velocities);
        const sd  = velocities.length > 1
            ? Math.sqrt(velocities.reduce((a, v) => a + Math.pow(v - avg, 2), 0) / (velocities.length - 1)).toFixed(1)
            : 0;
        lines.push([`AVG: ${avg} fps`,             `bold ${fs(20)} monospace`, '#60a5fa', 28 * s]);
        lines.push([`ES: ${es}  SD: ${sd}`,         `${fs(17)} monospace`,     '#9ca3af', 23 * s]);
    }

    // Measure widest line to set box width
    const HPAD = 20 * s, VTOP = 16 * s, VBOT = 14 * s;
    let maxW = 0;
    lines.forEach(([text, font]) => {
        ctx.font = font;
        maxW = Math.max(maxW, ctx.measureText(text).width);
    });
    const BOX_W = Math.ceil(maxW) + HPAD * 2;
    const BOX_H = VTOP + lines.reduce((sum, [,,, adv]) => sum + adv, 0) + VBOT;

    liveBoxDims.w = BOX_W;
    liveBoxDims.h = BOX_H;

    // Auto-position near centroid if not customized
    if (!liveBoxPos.customized && boxX === 0 && boxY === 0) {
        const cx = shots.reduce((a, s) => a + s.x, 0) / shots.length;
        const cy = shots.reduce((a, s) => a + s.y, 0) / shots.length;
        boxX = Math.min(cx + 20, canvas.width - BOX_W - 10);
        boxY = Math.max(cy - BOX_H / 2, 10);
        liveBoxPos.x = boxX;
        liveBoxPos.y = boxY;
    }

    // Draw background
    ctx.fillStyle = 'rgba(10, 10, 20, 0.88)';
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 3 * s;
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, BOX_W, BOX_H, 8 * s);
    ctx.fill();
    ctx.stroke();

    // Draw each line
    const px = boxX + HPAD;
    let py = boxY + VTOP;
    lines.forEach(([text, font, color, advance]) => {
        ctx.font = font;
        ctx.fillStyle = color;
        // offset baseline by approx ascent (80% of font size)
        const size = parseInt(font.match(/(\d+)px/)[1]);
        py += size * 0.82;
        ctx.fillText(text, px, py);
        py += advance - size * 0.82;
    });
}

function canvasScale() { return Math.max(1, canvas.width / 800); }

function drawConnections(shots, color, width) {
    if (!ctx) return;
    const s = canvasScale();
    ctx.strokeStyle = color; ctx.lineWidth = width * s;
    for (let i = 0; i < shots.length; i++) {
        for (let j = i + 1; j < shots.length; j++) {
            ctx.beginPath(); ctx.moveTo(shots[i].x, shots[i].y); ctx.lineTo(shots[j].x, shots[j].y); ctx.stroke();
        }
    }
    shots.forEach(p => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, 8 * s, 0, Math.PI * 2); ctx.fill(); });
}

function deleteGroup(idx) {
    groups.splice(idx, 1);
    updateSidebarList();
    redrawCanvas();
}

function updateSidebarList() {
    const list = document.getElementById('session-groups-list');
    const saveBtn  = document.getElementById('db-save-session-btn');
    const dlBtn    = document.getElementById('download-btn');
    const shareBtn = document.getElementById('share-btn');
    if (!list) return;

    if (groups.length === 0) {
        list.innerHTML = `<p class="text-xs text-gray-500 italic">No groups recorded in this session yet.</p>`;
        if (saveBtn)  saveBtn.classList.add('hidden');
        if (dlBtn)    dlBtn.classList.add('hidden');
        if (shareBtn) shareBtn.classList.add('hidden');
        return;
    }

    list.innerHTML = groups.map((g, idx) => {
        const velocities = g.shots.map(s => s.velocity).filter(v => v !== null);
        const avgVel = velocities.length > 0
            ? Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length)
            : null;
        const velLine = avgVel !== null
            ? `<span class="text-blue-400 font-mono">${avgVel} fps avg</span> · <span class="text-gray-500">${velocities.length} shots</span>`
            : `<span class="text-gray-500">${g.shots.length} shots · no chrono</span>`;

        return `
        <div class="bg-gray-900 border border-gray-700 rounded-lg p-3 space-y-1.5">
            <div class="flex justify-between items-start">
                <span class="text-[10px] font-bold uppercase tracking-wider text-amber-500">Group ${idx + 1}</span>
                <button onclick="deleteGroup(${idx})"
                    class="text-red-500 hover:text-red-400 text-[10px] font-bold cursor-pointer leading-none">✕ Remove</button>
            </div>
            <p class="text-xs font-bold text-white truncate">${g.gunText}</p>
            <p class="text-[11px] text-gray-400 truncate">${g.ammoText}</p>
            <div class="flex justify-between items-center pt-1 border-t border-gray-750">
                <span class="text-emerald-400 font-mono font-bold text-sm">${g.size}&quot;</span>
                <span class="text-[11px]">${velLine}</span>
            </div>
        </div>`;
    }).join('');

    if (saveBtn)  saveBtn.classList.remove('hidden');
    if (dlBtn)    dlBtn.classList.remove('hidden');
    if (shareBtn) shareBtn.classList.remove('hidden');
}
function saveForShare() {
    if (!canvas || groups.length === 0) return;

    const FOOTER_H = 60;
    const off = document.createElement('canvas');
    off.width  = canvas.width;
    off.height = canvas.height + FOOTER_H;
    const octx = off.getContext('2d');

    // Main annotated canvas (already has all stats boxes drawn)
    octx.drawImage(canvas, 0, 0);

    // Footer banner
    octx.fillStyle = '#050508';
    octx.fillRect(0, canvas.height, canvas.width, FOOTER_H);

    // Amber top edge
    octx.strokeStyle = '#f59e0b';
    octx.lineWidth = 2;
    octx.beginPath();
    octx.moveTo(0, canvas.height + 1);
    octx.lineTo(canvas.width, canvas.height + 1);
    octx.stroke();

    const dateStr = new Date().toISOString().slice(0, 10);
    const groupSummary = groups.map((g, i) => `G${i + 1}: ${g.size}"`).join('   ');
    const gunLabel = groups[0]?.gunText || '';

    const fontSize = Math.max(14, Math.min(22, Math.round(canvas.width / 55)));
    const midY = canvas.height + FOOTER_H / 2 + fontSize * 0.38;

    octx.font = `bold ${fontSize}px monospace`;
    octx.fillStyle = '#f59e0b';
    octx.textAlign = 'left';
    octx.fillText('🎯 ' + groupSummary, 20, midY);

    octx.font = `${Math.round(fontSize * 0.82)}px monospace`;
    octx.fillStyle = '#6b7280';
    octx.textAlign = 'right';
    octx.fillText((gunLabel ? gunLabel + '  ·  ' : '') + dateStr, canvas.width - 20, midY);
    octx.textAlign = 'left';

    const link = document.createElement('a');
    link.download = `range_session_${dateStr}.png`;
    link.href = off.toDataURL('image/png');
    link.click();
}
function downloadAnnotatedTarget() {
    if (!canvas || groups.length === 0) return;

    // Work on an offscreen copy so we don't dirty the live canvas
    const offscreen = document.createElement('canvas');
    offscreen.width = canvas.width;
    offscreen.height = canvas.height;
    const octx = offscreen.getContext('2d');

    // 1. Draw the base image
    octx.drawImage(imgElement, 0, 0);

    // 2. Re-draw all saved group lines & dots
    groups.forEach(g => {
        octx.strokeStyle = '#ef4444';
        octx.lineWidth = 6;
        for (let i = 0; i < g.shots.length; i++) {
            for (let j = i + 1; j < g.shots.length; j++) {
                octx.beginPath();
                octx.moveTo(g.shots[i].x, g.shots[i].y);
                octx.lineTo(g.shots[j].x, g.shots[j].y);
                octx.stroke();
            }
        }
        g.shots.forEach(p => {
            octx.fillStyle = '#ef4444';
            octx.beginPath();
            octx.arc(p.x, p.y, 8, 0, Math.PI * 2);
            octx.fill();
        });
    });

    // 3. Draw a stats legend box in the top-left corner
    const PAD = 18, LINE = 22, BOX_W = 340;
    const labelLines = groups.map((g, idx) => {
        const velocities = g.shots.map(s => s.velocity).filter(v => v !== null);
        const avgVel = velocities.length > 0
            ? Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length)
            : null;
        const velStr = avgVel !== null ? `  ${avgVel} fps avg` : '';
        return `G${idx + 1}: ${g.size}"  ·  ${g.gunText}${velStr}`;
    });

    const BOX_H = PAD * 2 + LINE * (labelLines.length + 1);
    octx.fillStyle = 'rgba(10, 10, 20, 0.82)';
    octx.strokeStyle = '#f59e0b';
    octx.lineWidth = 2;
    octx.beginPath();
    octx.roundRect(PAD, PAD, BOX_W, BOX_H, 8);
    octx.fill();
    octx.stroke();

    octx.font = 'bold 16px monospace';
    octx.fillStyle = '#f59e0b';
    octx.fillText('SESSION RESULTS', PAD + 14, PAD + LINE);

    octx.font = '14px monospace';
    octx.fillStyle = '#e5e7eb';
    labelLines.forEach((line, i) => {
        octx.fillText(line, PAD + 14, PAD + LINE * (i + 2));
    });

    // 4. Trigger download
    const link = document.createElement('a');
    const dateStr = new Date().toISOString().slice(0, 10);
    link.download = `target_session_${dateStr}.png`;
    link.href = offscreen.toDataURL('image/png');
    link.click();
}
async function commitSessionToDatabase() {
    if (groups.length === 0) return;

    const dateInput = document.getElementById('session-date');
    const sessionDate = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];

    const gunSelect = document.getElementById('select-gun');
    const ammoSelect = document.getElementById('select-ammo');

    const defaultGunId = gunSelect ? gunSelect.value : null;
    const defaultAmmoId = ammoSelect ? ammoSelect.value : null;

    if (!defaultGunId || !defaultAmmoId) {
        showToast("Please select a Firearm and Load Profile before saving to DB.", "error");
        return;
    }

    const saveBtn = document.getElementById('db-save-session-btn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerText = "Uploading…"; }

    // Resolve barrel ID — TC barrels are selected directly; regular firearms need a lookup
    let barrelId = null;
    const gunOption = gunSelect ? gunSelect.options[gunSelect.selectedIndex] : null;
    const isTC = gunOption && gunOption.dataset.type === 'tc';
    if (isTC) {
        barrelId = parseInt(defaultGunId);
    } else {
        try {
            const gunRes = await fetch(`/firearms/${defaultGunId}`);
            if (gunRes.ok) {
                const gunData = await gunRes.json();
                barrelId = gunData.barrels && gunData.barrels.length > 0 ? gunData.barrels[0].id : null;
            }
        } catch (_) {}
    }

    if (!barrelId) {
        showToast("Could not resolve barrel for selected platform.", "error");
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerText = "🚀 Upload Data to Homelab DB"; }
        return;
    }

    let successCount = 0;
    let failCount = 0;

    for (const g of groups) {
        const velocities = g.shots.map(s => s.velocity).filter(v => v !== null);
        const velocitiesCsv = velocities.length > 0 ? velocities.join(',') : '';

        // Build per-group image blob, respecting saved crop region
        let groupBlob = null;
        if (imgElement.src && imgElement.naturalWidth > 0) {
            if (g.cropRect && g.cropRect.w > 0 && g.cropRect.h > 0) {
                const off = document.createElement('canvas');
                off.width  = Math.round(g.cropRect.w);
                off.height = Math.round(g.cropRect.h);
                off.getContext('2d').drawImage(
                    canvas,
                    g.cropRect.x, g.cropRect.y, g.cropRect.w, g.cropRect.h,
                    0, 0, off.width, off.height
                );
                groupBlob = await new Promise(resolve => off.toBlob(resolve, 'image/jpeg', 0.88));
            } else {
                groupBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.88));
            }
        }

        const formData = new FormData();
        formData.append('barrel_id', barrelId);
        formData.append('ammo_id', defaultAmmoId);
        formData.append('date', sessionDate);
        formData.append('velocities_csv', velocitiesCsv);
        formData.append('group_size', g.size);
        if (groupBlob) formData.append('target_image', groupBlob, 'target.jpg');

        try {
            const res = await fetch('/performance-log/', { method: 'POST', body: formData });
            if (res.ok) { successCount++; } else { failCount++; }
        } catch (_) { failCount++; }
    }

    if (saveBtn) { saveBtn.disabled = false; saveBtn.innerText = "🚀 Upload Data to Homelab DB"; }

    if (failCount === 0) {
        showToast(`${successCount} group${successCount > 1 ? 's' : ''} committed to database.`);
        groups = [];
        updateSidebarList();
        redrawCanvas();
    } else {
        showToast(`${successCount} saved, ${failCount} failed. Check console for details.`, "error");
    }
}
function resetCanvas() { calibrationPoints = []; currentGroupShots = []; groups = []; pixelsPerInch = null; state = imgElement.src ? "calibrating" : "idle"; redrawCanvas(); }

async function loadCatalog(frameType = currentFrameType()) {
    const container = document.getElementById('catalog-container');
    if (!container) return;
    const url = `/catalog/?frame_type=${encodeURIComponent(frameType)}`;
    let all;
    try {
        const response = await fetch(url);
        if (!response.ok) { container.innerHTML = '<p class="text-red-400 italic text-sm">Failed to load catalog.</p>'; return; }
        all = await response.json();
    } catch(err) {
        container.innerHTML = '<p class="text-red-400 italic text-sm">Failed to load catalog.</p>';
        return;
    }
    const inventory = all.filter(g => currentCollectionFilter === 'sold' ? g.is_sold : !g.is_sold);

    document.getElementById('inventory-count').innerText = `${inventory.length} Platform${inventory.length !== 1 ? 's' : ''} Logged`;
    container.innerHTML = '';

    inventory.forEach(gun => {
        const content = document.createElement('div');
        content.className = "bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-xl hover:border-amber-500/50 transition";
        
        let statusLabelMarkup = gun.is_sold 
            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-950 text-red-400 border border-red-800">SOLD HISTORY ARCHIVE</span>`
            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800">${gun.frame_type || 'Rifle'}</span>`;
        
        // Fix: Properly map the image and caliber from your DB fields
        const targetSrc = gun.image_path_1 || "/static/images/placeholder.jpg";
        const caliberDisplay = gun.caliber || (gun.frame_type === "Barrel Only" ? "Modular Frame" : "Multi-Caliber Base");

        content.innerHTML = `
            <div class="w-full h-44 bg-gray-950 relative overflow-hidden cursor-pointer" onclick="window.location.href='firearm-detail.html?id=${gun.id}'">
                <img src="${targetSrc}" class="w-full h-full object-cover">
            </div>
            <div class="p-4 space-y-3">
                <div class="flex justify-between items-center">
                    ${statusLabelMarkup}
                    <span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-950 text-amber-400 border border-amber-800">${caliberDisplay}</span>
                </div>
                <div class="cursor-pointer hover:text-amber-400 transition" onclick="window.location.href='firearm-detail.html?id=${gun.id}'">
                    <h3 class="text-base font-bold text-white tracking-tight flex items-center gap-1">${gun.brand} ${gun.model}</h3>
                </div>
                <div class="border-t border-gray-700 pt-3 mt-2">
                    <p class="text-xs text-gray-400">Cost Basis: <span class="text-white font-mono">$${parseFloat(gun.price_paid || 0).toFixed(2)}</span></p>
                </div>
            </div>
        `;
        container.appendChild(content);
    });
}

const firearmForm = document.getElementById('firearm-form');
if (firearmForm) {
    firearmForm.addEventListener('submit', async (e) => {
        e.preventDefault(); const formData = new FormData(e.target);
        try {
            const response = await fetch('/firearms/', { method: 'POST', body: formData });
            if (response.ok) {
                const fd = formData;
                await Promise.all([
                    saveLookupValue('firearm_brand', fd.get('brand')),
                    saveLookupValue('firearm_model', fd.get('model')),
                    saveLookupValue('caliber',       fd.get('caliber')),
                ]);
                e.target.reset(); const ext = document.getElementById('tc-modular-extension'); if (ext) ext.classList.add('hidden');
                showToast('Hardware logged successfully.'); await fetchInitialLookupData(); switchTab('catalog-tab');
            } else {
                showToast('Asset data accepted locally for offline caching.', 'success');
                e.target.reset(); switchTab('catalog-tab');
            }
        } catch (err) { e.target.reset(); switchTab('catalog-tab'); }
    });
}

const shotgunForm = document.getElementById('shotgun-form');
if (shotgunForm) {
    shotgunForm.addEventListener('submit', async (e) => {
        e.preventDefault(); const formData = new FormData(e.target);
        try {
            const response = await fetch('/firearms/', { method: 'POST', body: formData });
            if (response.ok) {
                const fd = formData;
                await Promise.all([
                    saveLookupValue('firearm_brand', fd.get('brand')),
                    saveLookupValue('firearm_model', fd.get('model')),
                ]);
                e.target.reset(); showToast('Shotgun logged successfully.'); switchTab('catalog-tab');
            } else { showToast('Failed to save shotgun.', 'error'); }
        } catch (err) { showToast('Failed to save shotgun.', 'error'); }
    });
}

const handgunForm = document.getElementById('handgun-form');
if (handgunForm) {
    handgunForm.addEventListener('submit', async (e) => {
        e.preventDefault(); const formData = new FormData(e.target);
        try {
            const response = await fetch('/firearms/', { method: 'POST', body: formData });
            if (response.ok) {
                const fd = formData;
                await Promise.all([
                    saveLookupValue('firearm_brand', fd.get('brand')),
                    saveLookupValue('firearm_model', fd.get('model')),
                    saveLookupValue('caliber',       fd.get('caliber')),
                ]);
                e.target.reset(); showToast('Handgun logged successfully.'); switchTab('catalog-tab');
            } else { showToast('Failed to save handgun.', 'error'); }
        } catch (err) { showToast('Failed to save handgun.', 'error'); }
    });
}

const factoryAmmoForm = document.getElementById('ammo-factory-form');
if (factoryAmmoForm) {
    factoryAmmoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        try {
            const response = await fetch('/ammo/', { method: 'POST', body: formData });
            if (response.ok) {
                await Promise.all([
                    saveLookupValue('ammo_brand', formData.get('brand')),
                    saveLookupValue('caliber',    formData.get('caliber')),
                ]);
                e.target.reset();
                showToast('Factory load registered.');
            } else {
                showToast('Failed to save ammo load.', 'error');
            }
        } catch (err) {
            showToast('Error saving ammo load.', 'error');
        }
    });
}

const handloadForm = document.getElementById('ammo-handload-form');
if (handloadForm) {
    handloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        formData.set('is_handload', 'true');
        try {
            const response = await fetch('/ammo/', { method: 'POST', body: formData });
            if (!response.ok) { showToast('Failed to save handload recipe.', 'error'); return; }

            await Promise.all([
                saveLookupValue('caliber',          formData.get('caliber')),
                saveLookupValue('handload_powder',  formData.get('powder_id')),
                saveLookupValue('handload_primer',  formData.get('primer_id')),
                saveLookupValue('handload_bullet',  formData.get('bullet_id')),
                saveLookupValue('handload_brass',   formData.get('brass_brand')),
            ]);

            // Run component deduction if the section was filled out
            const rounds = parseInt(formData.get('rounds_loaded'));
            const powderCharge = parseFloat(formData.get('powder_charge'));
            const powderId = formData.get('deduct_powder_id');
            const primerId = formData.get('deduct_primer_id');
            const bulletId = formData.get('deduct_bullet_id');
            const casingId = formData.get('deduct_casing_id');

            const hasDeduction = rounds > 0 && (powderId || primerId || bulletId || casingId);
            if (hasDeduction) {
                const payload = {
                    rounds_loaded: rounds,
                    powder_charge_gr: powderCharge || null,
                    powder_inv_id: powderId ? parseInt(powderId) : null,
                    primer_inv_id: primerId ? parseInt(primerId) : null,
                    bullet_inv_id: bulletId ? parseInt(bulletId) : null,
                    casing_inv_id: casingId ? parseInt(casingId) : null,
                };
                const dRes = await fetch('/components/deduct/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (dRes.ok) {
                    const { warnings } = await dRes.json();
                    warnings.forEach(w => showToast(w, 'error'));
                }
            }

            e.target.reset();
            // Collapse deduct section and reset toggle
            const ds = document.getElementById('deduct-section');
            const di = document.getElementById('deduct-toggle-icon');
            if (ds) ds.classList.add('hidden');
            if (di) di.textContent = '▶';
            showToast('Handload committed.' + (hasDeduction ? ` Inventory updated for ${rounds} rounds.` : ''));
        } catch (err) {
            showToast('Error saving handload recipe.', 'error');
        }
    });
}

const tcReceiverForm = document.getElementById('tc-receiver-form');
if (tcReceiverForm) {
    tcReceiverForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        try {
            const res = await fetch('/tc-receivers/', { method: 'POST', body: formData });
            if (res.ok) {
                e.target.reset();
                showToast('TC Receiver registered.');
                switchTab('catalog-tab');
                switchPlatformTab('tc');
            } else {
                showToast('Failed to register TC Receiver.', 'error');
            }
        } catch (err) { showToast('Error saving TC Receiver.', 'error'); }
    });
}

const tcBarrelForm = document.getElementById('tc-barrel-form');
if (tcBarrelForm) {
    tcBarrelForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        // Convert string "true"/"false" booleans from select elements
        formData.set('is_threaded', formData.get('is_threaded') === 'true');
        formData.set('has_muzzle_brake', formData.get('has_muzzle_brake') === 'true');
        try {
            const res = await fetch('/tc-barrels/', { method: 'POST', body: formData });
            if (res.ok) {
                e.target.reset();
                showToast('TC Barrel registered.');
                switchTab('catalog-tab');
                switchPlatformTab('tc');
            } else {
                showToast('Failed to register TC Barrel.', 'error');
            }
        } catch (err) { showToast('Error saving TC Barrel.', 'error'); }
    });
}

async function toggleScopeAddMount() {
    const sel = document.getElementById('scope-add-installed');
    const mountSel = document.getElementById('scope-add-mount-select');
    if (!sel || !mountSel) return;

    if (sel.value === 'yes') {
        mountSel.classList.remove('hidden');
        if (mountSel.options.length <= 1) {
            // Lazy-load available mounts (no scope yet, so no for_scope_id filter needed)
            try {
                const res = await fetch('/available-mounts/');
                const data = res.ok ? await res.json() : { firearms: [], tc_barrels: [] };
                let opts = `<option value="">-- Select Platform --</option>`;
                if (data.firearms.length > 0) {
                    opts += `<optgroup label="── Rifles ──">` +
                        data.firearms.map(f => `<option value="firearm:${f.id}">${f.label}</option>`).join('') +
                        `</optgroup>`;
                }
                if (data.tc_barrels.length > 0) {
                    opts += `<optgroup label="── TC Barrels ──">` +
                        data.tc_barrels.map(b => `<option value="barrel:${b.id}">${b.label}</option>`).join('') +
                        `</optgroup>`;
                }
                mountSel.innerHTML = opts;
            } catch(_) {}
        }
    } else {
        mountSel.classList.add('hidden');
    }
}

const addScopeForm = document.getElementById('add-scope-form');
if (addScopeForm) {
    addScopeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const installedSel = document.getElementById('scope-add-installed');
        const mountSel     = document.getElementById('scope-add-mount-select');

        try {
            const res = await fetch('/scopes/', { method: 'POST', body: formData });
            if (!res.ok) { showToast('Failed to register scope.', 'error'); return; }
            const scope = await res.json();
            await Promise.all([
                saveLookupValue('scope_brand', formData.get('brand')),
                saveLookupValue('scope_model', formData.get('model')),
            ]);

            // Mount immediately if the user chose a platform
            if (installedSel?.value === 'yes' && mountSel?.value) {
                const [type, id] = mountSel.value.split(':');
                await fetch(`/scopes/${scope.id}/mount`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mount_type: type, mount_id: parseInt(id) })
                });
            }

            e.target.reset();
            // Reset the mount UI
            if (installedSel) installedSel.value = 'no';
            if (mountSel) { mountSel.innerHTML = '<option value="">Loading platforms…</option>'; mountSel.classList.add('hidden'); }

            showToast('Scope registered.');
            switchTab('catalog-tab');
            switchInventoryTab('optics');
        } catch (err) { showToast('Error saving scope.', 'error'); }
    });
}

// ── Add Inventory: switchFormCategory + Components ────────────────────────────

function switchAddComponent(formId) {
    document.querySelectorAll('.add-component-form').forEach(f => f.classList.add('hidden'));
    const formMap = { 'add-powder': 'powder-form', 'add-primer': 'primer-form', 'add-bullet-comp': 'bullet-comp-form', 'add-casing': 'casing-form' };
    document.getElementById(formMap[formId])?.classList.remove('hidden');
    const btnMap = { 'add-powder': 'btn-add-powder', 'add-primer': 'btn-add-primer', 'add-bullet-comp': 'btn-add-bullet-comp', 'add-casing': 'btn-add-casing' };
    Object.entries(btnMap).forEach(([key, btnId]) => {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.className = key === formId
            ? "px-3 py-1.5 text-xs font-bold rounded bg-emerald-600 text-white cursor-pointer"
            : "px-3 py-1.5 text-xs font-bold rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    });
}

function toggleDeductSection() {
    const section = document.getElementById('deduct-section');
    const icon = document.getElementById('deduct-toggle-icon');
    const isHidden = section.classList.contains('hidden');
    section.classList.toggle('hidden');
    icon.textContent = isHidden ? '▼' : '▶';
    if (isHidden) loadDeductionDropdowns();
}

async function loadDeductionDropdowns() {
    const [powders, primers, bullets, casings] = await Promise.all([
        fetch('/components/powders/').then(r => r.ok ? r.json() : []),
        fetch('/components/primers/').then(r => r.ok ? r.json() : []),
        fetch('/components/bullets/').then(r => r.ok ? r.json() : []),
        fetch('/components/casings/').then(r => r.ok ? r.json() : []),
    ]);

    const pSel = document.getElementById('deduct-powder-select');
    const prSel = document.getElementById('deduct-primer-select');
    const bSel = document.getElementById('deduct-bullet-select');
    const cSel = document.getElementById('deduct-casing-select');

    if (pSel) {
        pSel.innerHTML = '<option value="">— Skip powder deduction —</option>' +
            powders.map(p => `<option value="${p.id}">${p.brand} ${p.name} (${p.weight_lbs} lbs)</option>`).join('');
    }
    if (prSel) {
        prSel.innerHTML = '<option value="">— Skip primer deduction —</option>' +
            primers.map(p => `<option value="${p.id}">${p.brand} ${p.primer_type} (${p.quantity} ct)</option>`).join('');
    }
    if (bSel) {
        bSel.innerHTML = '<option value="">— Skip bullet deduction —</option>' +
            bullets.map(b => `<option value="${b.id}">${b.brand} ${b.caliber} ${b.weight_gr}gr (${b.quantity} ct)</option>`).join('');
    }
    if (cSel) {
        cSel.innerHTML = '<option value="">— Skip casing deduction —</option>' +
            casings.map(c => `<option value="${c.id}">${c.brand} ${c.caliber} ${c.condition_label} (${c.quantity} ct)</option>`).join('');
    }
}

const powderForm = document.getElementById('powder-form');
if (powderForm) {
    powderForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            const res = await fetch('/components/powders/', { method: 'POST', body: fd });
            if (res.ok) {
                await Promise.all([saveLookupValue('powder_brand', fd.get('brand')), saveLookupValue('powder_name', fd.get('name'))]);
                e.target.reset(); showToast('Powder logged.'); switchTab('catalog-tab'); switchInventoryTab('components'); switchComponentFilter('powders');
            } else showToast('Failed to log powder.', 'error');
        } catch(_) { showToast('Error saving powder.', 'error'); }
    });
}

const primerForm = document.getElementById('primer-form');
if (primerForm) {
    primerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            const res = await fetch('/components/primers/', { method: 'POST', body: fd });
            if (res.ok) {
                await saveLookupValue('primer_brand', fd.get('brand'));
                e.target.reset(); showToast('Primers logged.'); switchTab('catalog-tab'); switchInventoryTab('components'); switchComponentFilter('primers');
            } else showToast('Failed to log primers.', 'error');
        } catch(_) { showToast('Error saving primers.', 'error'); }
    });
}

const bulletCompForm = document.getElementById('bullet-comp-form');
if (bulletCompForm) {
    bulletCompForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            const res = await fetch('/components/bullets/', { method: 'POST', body: fd });
            if (res.ok) {
                await Promise.all([
                    saveLookupValue('bullet_brand', fd.get('brand')),
                    saveLookupValue('bullet_product_line', fd.get('product_line')),
                    saveLookupValue('caliber', fd.get('caliber')),
                ]);
                e.target.reset(); showToast('Bullets logged.'); switchTab('catalog-tab'); switchInventoryTab('components'); switchComponentFilter('bullets');
            } else showToast('Failed to log bullets.', 'error');
        } catch(_) { showToast('Error saving bullets.', 'error'); }
    });
}

const casingForm = document.getElementById('casing-form');
if (casingForm) {
    casingForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            const res = await fetch('/components/casings/', { method: 'POST', body: fd });
            if (res.ok) {
                await Promise.all([
                    saveLookupValue('casing_brand', fd.get('brand')),
                    saveLookupValue('caliber', fd.get('caliber')),
                ]);
                e.target.reset(); showToast('Casings logged.'); switchTab('catalog-tab'); switchInventoryTab('components'); switchComponentFilter('casings');
            } else showToast('Failed to log casings.', 'error');
        } catch(_) { showToast('Error saving casings.', 'error'); }
    });
}

async function applyPreferences() {
    try {
        const res = await fetch('/api/preferences/');
        if (!res.ok) return;
        const prefs = await res.json();
        const off = (key) => prefs[key] === 'false';
        const hide = (...ids) => ids.forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('hidden'); });

        if (off('feat_shotguns'))  hide('plat-btn-shotgun', 'btn-add-shotgun');
        if (off('feat_handguns'))  hide('plat-btn-handgun', 'btn-add-handgun');
        if (off('feat_tc'))        hide('plat-btn-tc', 'btn-add-tc-receiver', 'btn-add-tc-barrel');
        if (off('feat_reloading')) hide('inv-btn-components', 'btn-cat-components');
        if (off('feat_ammo_log'))  hide('inv-btn-ammo', 'btn-cat-ammunition', 'nav-btn-measure', 'nav-btn-measure-mobile');
    } catch (_) {}
}

window.onload = () => { fetchInitialLookupData(); loadCatalog(); applyPreferences(); };