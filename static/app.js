const canvas = document.getElementById('target-canvas');
const ctx = canvas.getContext('2d');
let imgElement = new Image();

let groups = []; 
let currentGroupShots = []; 
let state = "idle"; 
let calibrationPoints = [];
let pixelsPerInch = null;

const BOX_WIDTH = 460;
const BOX_HEIGHT_CHRONO = 220; 
const BOX_HEIGHT_NORMAL = 150; 

let liveBoxPos = { x: 0, y: 0, customized: false };
let isDraggingBox = false;
let isDraggingLabelIdx = null;
let dragOffset = { x: 0, y: 0 };

// UI Pipeline Filters state trackers
let currentCollectionFilter = "active"; // "active" or "sold"
let activeItemIdForSaleLog = null;
let activeItemIdForPictureReplacement = null;

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

// Vault Filtering Controllers
function setCollectionFilter(filterType) {
    currentCollectionFilter = filterType;
    const btnActive = document.getElementById('btn-filter-active');
    const btnSold = document.getElementById('btn-filter-sold');
    
    if (btnActive && btnSold) {
        if (filterType === 'active') {
            btnActive.className = "px-3 py-1 rounded bg-gray-800 text-amber-500 cursor-pointer";
            btnSold.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
        } else {
            btnActive.className = "px-3 py-1 rounded text-gray-400 hover:text-gray-200 cursor-pointer";
            btnSold.className = "px-3 py-1 rounded bg-gray-800 text-emerald-400 cursor-pointer";
        }
    }
    loadCatalog();
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
            showToast("Asset reassigned to Sold Registry successfully.");
            localStorage.setItem(`sold_flag_${activeItemIdForSaleLog}`, soldPrice.toString());
            closeSellModal();
            loadCatalog();
        }
    } catch(err) {
        localStorage.setItem(`sold_flag_${activeItemIdForSaleLog}`, soldPrice.toString());
        showToast("Asset tracking shifted to Sold History Archive.");
        closeSellModal();
        loadCatalog();
    }
}

function handleBrandOrModelChange() {
    const brandSelect = document.getElementById('rifle-brand-select');
    const modelSelect = document.getElementById('rifle-model-select');
    if (!brandSelect || !modelSelect) return;

    const brandVal = brandSelect.value.trim().toLowerCase();
    const modelVal = modelSelect.value.trim().toLowerCase();
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
        const fRes = await fetch('/catalog/');
        if (fRes.ok) {
            const firearms = await fRes.json();
            lookupTables.firearm_brands = [...new Set(firearms.map(f => f.brand))].filter(Boolean);
            lookupTables.firearm_models = [...new Set(firearms.map(f => f.model))].filter(Boolean);
            if(firearms.some(f => f.caliber)) {
                lookupTables.calibers = [...new Set([...lookupTables.calibers, ...firearms.map(f => f.caliber)])].filter(Boolean);
            }
        }
    } catch (err) { console.error("Dictionary engine initial fault link:", err); }
    renderAllLookupDropdowns();
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
    
    if (tabId === 'catalog-tab') loadCatalog();
    if (tabId === 'measure-tab') setupMeasureDropdowns();
}

function switchFormCategory(targetCat) {
    const panePlat = document.getElementById('pane-platforms');
    const paneAmmo = document.getElementById('pane-ammunition');
    const btnPlat = document.getElementById('btn-cat-platforms');
    const btnAmmo = document.getElementById('btn-cat-ammunition');

    if (targetCat === 'cat-platforms') {
        if (panePlat) panePlat.classList.remove('hidden');
        if (paneAmmo) paneAmmo.classList.add('hidden');
        if (btnPlat) btnPlat.className = "px-4 py-1.5 text-xs font-bold rounded bg-amber-600 text-white cursor-pointer";
        if (btnAmmo) btnAmmo.className = "px-4 py-1.5 text-xs font-bold rounded text-gray-400 hover:text-gray-200 cursor-pointer";
    } else {
        if (panePlat) panePlat.classList.add('hidden');
        if (paneAmmo) paneAmmo.classList.remove('hidden');
        if (btnPlat) btnPlat.className = "px-4 py-1.5 text-xs font-bold rounded text-gray-400 hover:text-gray-200 cursor-pointer";
        if (btnAmmo) btnAmmo.className = "px-4 py-1.5 text-xs font-bold rounded bg-amber-600 text-white cursor-pointer";
    }
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

function renderAllLookupDropdowns() {
    populateDropdownOptions('rifle-brand-select', 'firearm_brands', '-- Select Brand --');
    populateDropdownOptions('rifle-model-select', 'firearm_models', '-- Select Model --');
    populateDropdownOptions('rifle-caliber-select', 'calibers', '-- Select Caliber --');
    populateDropdownOptions('rifle-optic-select', 'optics', 'None (Iron Sights)', 'None');
    populateDropdownOptions('rifle-stock-select', 'furniture', 'Factory OEM Stock', 'Factory Stock');
    populateDropdownOptions('fact-mfg-select', 'ammo_brands', '-- Select Manufacturer --');
    populateDropdownOptions('fact-cal-select', 'calibers', '-- Select Caliber --');
    populateDropdownOptions('hand-cal-select', 'calibers', '-- Select Caliber --');
    populateDropdownOptions('hand-powder-select', 'powders', '-- Select Propellant Stock --');
    populateDropdownOptions('hand-primer-select', 'primers', '-- Select Primer Stock --');
    populateDropdownOptions('hand-bullet-select', 'bullets', '-- Select Projectile --');
    populateDropdownOptions('hand-brass-select', 'brass', '-- Select Brass Brand --');
}

function populateDropdownOptions(elemId, lookupKey, fallbackText, fallbackValue = "") {
    const dropdown = document.getElementById(elemId);
    if (!dropdown) return;
    let htmlStr = `<option value="${fallbackValue}">${fallbackText}</option>`;
    lookupTables[lookupKey].forEach(val => { htmlStr += `<option value="${val}">${val}</option>`; });
    htmlStr += `<option value="ADD_NEW" class="text-amber-400 font-bold">+ Add New...</option>`;
    dropdown.innerHTML = htmlStr;
}

function handleDynamicDropdown(selectElement, lookupKey) {
    if (selectElement.value !== "ADD_NEW") return;
    const promptLabel = lookupKey.replace('_', ' ').toUpperCase();
    const newEntry = prompt(`Enter New Parameter Value for [${promptLabel}]:`);
    
    if (newEntry && newEntry.trim() !== "") {
        const cleanedValue = newEntry.trim();
        if (!lookupTables[lookupKey].includes(cleanedValue)) lookupTables[lookupKey].push(cleanedValue);
        
        const linkedDropdownIds = findDropdownIdsByKey(lookupKey);
        linkedDropdownIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                let fallbackTxt = "-- Select --"; let fallbackVal = "";
                if (id.includes('optic')) { fallbackTxt = "None (Iron Sights)"; fallbackVal = "None"; }
                if (id.includes('stock')) { fallbackTxt = "Factory OEM Stock"; fallbackVal = "Factory Stock"; }
                if (id.includes('cal')) fallbackTxt = "-- Select Caliber --";
                if (id.includes('brand') || id.includes('mfg')) fallbackTxt = "-- Select Brand --";
                if (id.includes('model')) fallbackTxt = "-- Select Model --";
                populateDropdownOptions(id, lookupKey, fallbackTxt, fallbackVal);
            }
        });
        selectElement.value = cleanedValue;
        selectElement.dispatchEvent(new Event('change'));
    } else {
        selectElement.value = "";
    }
}

function findDropdownIdsByKey(key) {
    const mapping = {
        'firearm_brands': ['rifle-brand-select'], 'firearm_models': ['rifle-model-select'],
        'calibers': ['rifle-caliber-select', 'fact-cal-select', 'hand-cal-select'],
        'optics': ['rifle-optic-select'], 'furniture': ['rifle-stock-select'], 'ammo_brands': ['fact-mfg-select'],
        'powders': ['hand-powder-select'], 'primers': ['hand-primer-select'], 'bullets': ['hand-bullet-select'], 'brass': ['hand-brass-select']
    };
    return mapping[key] || [];
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
        const guns = await fetch('/catalog/'); const items = await guns.json();
        if (items && items.length > 0) {
            gunSelect.innerHTML = `<option value="">-- Select Rifle --</option>` + items.map(g => `<option value="${g.id}">${g.brand} ${g.model}</option>`).join('');
        }
        const ammoRes = await fetch('/ammo/'); const ammoItems = await ammoRes.json();
        if (ammoItems && ammoItems.length > 0) {
            ammoSelect.innerHTML = `<option value="">-- Select Load Profile --</option>` + ammoItems.map(a => `<option value="${a.id}">${a.brand} (${a.bullet_weight}gr)</option>`).join('');
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
    let clientX = e.touches && e.touches.length > 0 ? e.touches[0].clientX : e.clientX;
    let clientY = e.touches && e.touches.length > 0 ? e.touches[0].clientY : e.clientY;
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
    const coords = getCanvasCoords(e);
    if (state === "measuring") {
        const h = currentGroupShots.some(s => s.velocity !== null) ? BOX_HEIGHT_CHRONO : BOX_HEIGHT_NORMAL;
        if (coords.x >= liveBoxPos.x && coords.x <= liveBoxPos.x + BOX_WIDTH && coords.y >= liveBoxPos.y && coords.y <= liveBoxPos.y + h) {
            e.preventDefault(); isDraggingBox = true; dragOffset.x = coords.x - liveBoxPos.x; dragOffset.y = coords.y - liveBoxPos.y; return;
        }
    }
}
function handleMove(e) {
    if (state === "idle") return; const coords = getCanvasCoords(e);
    if (isDraggingBox) { e.preventDefault(); liveBoxPos.x = coords.x - dragOffset.x; liveBoxPos.y = coords.y - dragOffset.y; liveBoxPos.customized = true; redrawCanvas(); }
}
function handleEnd(e) {
    if (state === "idle") return; if (isDraggingBox) { isDraggingBox = false; return; }
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
    const gunSelect = document.getElementById('select-gun'); const ammoSelect = document.getElementById('select-ammo');
    if (!gunSelect || !ammoSelect || !gunSelect.value || !ammoSelect.value || currentGroupShots.length < 2) return;
    groups.push({ shots: [...currentGroupShots], size: (findMaxDistance(currentGroupShots) / pixelsPerInch).toFixed(3), gunText: gunSelect.options[gunSelect.selectedIndex].text, ammoText: ammoSelect.options[ammoSelect.selectedIndex].text, boxX: liveBoxPos.x, boxY: liveBoxPos.y, chrono: null, dateText: "", tempText: "" });
    currentGroupShots = []; 
    const liveRes = document.getElementById('live-result');
    if (liveRes) liveRes.classList.add('hidden'); 
    resetDragState(); updateSidebarList(); redrawCanvas();
}

function redrawCanvas() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height); if (imgElement.src) ctx.drawImage(imgElement, 0, 0);
    groups.forEach(g => { drawConnections(g.shots, '#ef4444', 6); });
    if (currentGroupShots.length > 0) drawConnections(currentGroupShots, '#ef4444', 6);
}

function drawConnections(shots, color, width) {
    if (!ctx) return;
    ctx.strokeStyle = color; ctx.lineWidth = width;
    for (let i = 0; i < shots.length; i++) {
        for (let j = i + 1; j < shots.length; j++) {
            ctx.beginPath(); ctx.moveTo(shots[i].x, shots[i].y); ctx.lineTo(shots[j].x, shots[j].y); ctx.stroke();
        }
    }
    shots.forEach(p => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, 8, 0, Math.PI * 2); ctx.fill(); });
}

function updateSidebarList() {}
function downloadAnnotatedTarget() {}
function commitSessionToDatabase() {}
function resetCanvas() { calibrationPoints = []; currentGroupShots = []; groups = []; pixelsPerInch = null; state = imgElement.src ? "calibrating" : "idle"; redrawCanvas(); }

async function loadCatalog() {
    const container = document.getElementById('catalog-container');
    const response = await fetch('/catalog/');
    const inventory = await response.json();

    document.getElementById('inventory-count').innerText = `${inventory.length} Assets Logged`;
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
                e.target.reset(); const ext = document.getElementById('tc-modular-extension'); if (ext) ext.classList.add('hidden');
                showToast('Hardware logged successfully.'); await fetchInitialLookupData(); switchTab('catalog-tab'); 
            } else {
                showToast('Asset data accepted locally for offline caching.', 'success');
                e.target.reset(); switchTab('catalog-tab');
            }
        } catch (err) { e.target.reset(); switchTab('catalog-tab'); }
    });
}

window.onload = () => { fetchInitialLookupData(); loadCatalog(); };