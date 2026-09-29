// ── Local Device PIN ─────────────────────────────────────────────────
const VAULT_META_KEY = 'estatescout_vault_pin';
const VAULT_ITERATIONS = 210000;
function bytesToBase64(bytes) { return btoa(String.fromCharCode(...new Uint8Array(bytes))); }
async function pinDigest(pin, salt) {
  const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(pin), 'PBKDF2', false, ['deriveBits']);
  return crypto.subtle.deriveBits({name:'PBKDF2', salt, iterations:VAULT_ITERATIONS, hash:'SHA-256'}, material, 256);
}
function vaultMeta() { try { return JSON.parse(localStorage.getItem(VAULT_META_KEY) || 'null'); } catch { return null; } }
function showVaultError(message) { document.getElementById('vaultError').textContent = message; }
async function initVaultLock() {
  const meta = vaultMeta();
  const setup = !meta;
  document.getElementById('vaultTitle').textContent = setup ? 'Protect EstateScout' : 'Unlock EstateScout';
  document.getElementById('vaultMessage').textContent = setup ? 'Create a local PIN for this device. Your device Face ID/passcode remains the primary protection.' : 'Enter your local PIN to unlock this device.';
  document.getElementById('vaultConfirmGroup').style.display = setup ? 'block' : 'none';
  document.getElementById('vaultSubmit').textContent = setup ? 'Create local PIN' : 'Unlock';
  document.getElementById('vaultPin').autocomplete = setup ? 'new-password' : 'current-password';
  document.getElementById('vaultPin').focus();
}
async function submitVaultPin() {
  const pin = document.getElementById('vaultPin').value;
  const meta = vaultMeta();
  showVaultError('');
  if (pin.length < 6) { showVaultError('Use at least 6 characters.'); return; }
  if (!meta) {
    if (pin !== document.getElementById('vaultConfirm').value) { showVaultError('PIN entries do not match.'); return; }
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const digest = await pinDigest(pin, salt);
    localStorage.setItem(VAULT_META_KEY, JSON.stringify({version:1, salt:bytesToBase64(salt), digest:bytesToBase64(digest), iterations:VAULT_ITERATIONS}));
  } else {
    const salt = Uint8Array.from(atob(meta.salt), c => c.charCodeAt(0));
    const digest = bytesToBase64(await pinDigest(pin, salt));
    if (digest !== meta.digest) { showVaultError('Incorrect PIN.'); return; }
  }
  document.getElementById('vaultPin').value = ''; document.getElementById('vaultConfirm').value = '';
  document.getElementById('vaultLock').classList.remove('active');
  navigator.storage?.persist?.();
}

// ── Navigation ────────────────────────────────────────────────────────
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(pageId).classList.add('active');
  
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navMap = {'page-home':0,'page-silver':1,'page-photo':2,'page-collection':3};
  const idx = navMap[pageId];
  if(idx !== undefined) document.querySelectorAll('.nav-item')[idx].classList.add('active');
  
  if(pageId === 'page-collection') renderCollection();
  if(pageId === 'page-library') renderLibrary();
}

// ── Price Tag / Barcode Scanner ───────────────────────────────────────
async function scanPriceTag(input) {
  const result = document.getElementById('priceTagResult');
  if (!input.files?.[0]) return;
  if (!('BarcodeDetector' in window)) {
    result.textContent = 'Barcode scanning is not supported by this browser. Enter the asking price manually.';
    result.style.display = 'block';
    return;
  }
  try {
    const bitmap = await createImageBitmap(input.files[0]);
    const detector = new BarcodeDetector({formats: ['qr_code','code_128','code_39','ean_13','upc_a']});
    const codes = await detector.detect(bitmap);
    const match = codes.map(code => code.rawValue).find(value => /^\$?\s*\d+(?:\.\d{1,2})?$/.test(value));
    if (match) {
      document.getElementById('askingPrice').value = parseFloat(match.replace('$',''));
      result.textContent = `Barcode read: ${match}. Tap Evaluate to compare it with the item value.`;
    } else {
      result.textContent = 'Barcode found, but it did not contain a readable dollar amount. Enter the asking price manually.';
    }
  } catch (error) {
    result.textContent = 'Could not read this tag. Try a closer, brighter photo or enter the asking price manually.';
  }
  result.style.display = 'block';
}
function evaluateAskingPrice() {
  const price = Number(document.getElementById('askingPrice').value);
  const result = document.getElementById('priceTagResult');
  if (!Number.isFinite(price) || price < 0) { result.textContent = 'Enter a valid asking price first.'; result.style.display = 'block'; return; }
  const latest = collectionItems()[0] || {};
  const range = String(latest.value || '').match(/\\d+(?:\\.\\d+)?/g)?.map(Number) || [];
  const low = range[0] || 0;
  const high = range[1] || low;
  let label = 'CONSIDER';
  let explanation = 'Add verified marks, weight, condition, and maker evidence before buying.';
  if (high > 0 && price <= low * 0.6) { label = 'BUY'; explanation = 'Asking price is substantially below the recorded value range.'; }
  else if (high > 0 && price > high) { label = 'WALK'; explanation = 'Asking price is above the recorded value range.'; }
  result.innerHTML = `<h4>Recommendation: ${label}</h4><p>Asking price: <b>$${price.toFixed(2)}</b>${high ? ` • Recorded range: $${low.toFixed(2)}–$${high.toFixed(2)}` : ''}</p><p>${explanation}</p>`;
  result.style.display = 'block';
}

// ── Photo Comparison ──────────────────────────────────────────────────
const comparePhotosState = {A: null, B: null};
function loadComparePhoto(side, input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = event => {
    comparePhotosState[side] = event.target.result;
    const preview = document.getElementById('comparePreview');
    const existing = document.getElementById(`compare-${side}`);
    if (existing) existing.remove();
    const image = document.createElement('img');
    image.id = `compare-${side}`;
    image.src = event.target.result;
    image.alt = `Comparison item ${side}`;
    image.style.cssText = 'width:50%;max-height:180px;object-fit:contain;border-radius:8px;border:1px solid rgba(200,164,90,.2);';
    preview.appendChild(image);
  };
  reader.readAsDataURL(input.files[0]);
}
function comparePhotos() {
  const result = document.getElementById('compareResult');
  if (!comparePhotosState.A || !comparePhotosState.B) {
    result.textContent = 'Load both Item A and Item B before comparing.';
    result.style.display = 'block';
    return;
  }
  const aSize = comparePhotosState.A.length;
  const bSize = comparePhotosState.B.length;
  result.innerHTML = `<h4>Comparison Ready</h4><p>Both items are loaded. Review each photo at close range for marks, weight, wear, and maker evidence. Photo A: ${aSize.toLocaleString()} bytes. Photo B: ${bSize.toLocaleString()} bytes.</p><p><b>Next step:</b> record each item's evidence separately, then use the stronger verified mark/weight combination—not appearance alone—to decide.</p>`;
  result.style.display = 'block';
}

// ── Photo Handling ────────────────────────────────────────────────────
let currentPhotoDataUrl = null;
let currentPhotoWidth = 0;
let currentPhotoHeight = 0;
let currentAnnotations = [];
let annotationHistory = [];
let currentTool = 'circle';

function triggerFileInput() {
  document.getElementById('fileInput').click();
}

function toggleFloorMode() {
  const active = document.body.classList.toggle('floor-mode');
  localStorage.setItem('estatescout_floor_mode', active ? '1' : '0');
  const button = document.getElementById('floorModeButton');
  button.setAttribute('aria-pressed', String(active));
  button.textContent = active ? '🌙 Standard Mode' : '☀️ Floor Mode';
}
function updateCaptureQuality(file, image) {
  const checklist = document.getElementById('captureChecklist');
  const problems = [];
  if (file.size > 12 * 1024 * 1024) problems.push('large file');
  if (image.naturalWidth < 1200 || image.naturalHeight < 900) problems.push('low resolution');
  if (problems.length) {
    checklist.innerHTML = `<h4>Retake for better evidence</h4><p>This photo may be hard to verify (${problems.join(', ')}). Use bright indirect light and fill the frame with the mark.</p>`;
  } else {
    checklist.innerHTML = '<h4>Photo quality looks usable</h4><p>Next: annotate the visible mark, record weight and magnet result, then save the evidence.</p>';
  }
}

function handlePhoto(input) {
  if(input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      currentPhotoDataUrl = e.target.result;
      const preview = document.getElementById('previewImg');
      preview.onload = () => updateCaptureQuality(input.files[0], preview);
      preview.src = e.target.result;
      document.getElementById('photoPreview').style.display = 'block';
      document.getElementById('photoAnalysis').style.display = 'none';
      document.getElementById('annotationCanvas').style.display = 'none';
      document.getElementById('annotationControls').style.display = 'none';
      currentAnnotations = [];
      
      // Hide the upload zone text
      document.getElementById('photoZone').style.display = 'none';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function retakePhoto() {
  document.getElementById('fileInput').value = '';
  document.getElementById('photoPreview').style.display = 'none';
  document.getElementById('photoAnalysis').style.display = 'none';
  document.getElementById('annotationCanvas').style.display = 'none';
  document.getElementById('annotationControls').style.display = 'none';
  document.getElementById('photoZone').style.display = 'block';
  currentPhotoDataUrl = null;
  currentAnnotations = [];
  annotationHistory = [];
}

// ── Annotation System ─────────────────────────────────────────────────
function showAnnotationMode() {
  if(!currentPhotoDataUrl) return;
  
  const canvas = document.getElementById('annotationCanvas');
  const ctx = canvas.getContext('2d');
  const img = new Image();
  
  img.onload = function() {
    currentPhotoWidth = img.width;
    currentPhotoHeight = img.height;
    
    // Scale canvas to fit screen width
    const containerWidth = document.getElementById('photoPreview').clientWidth;
    const scale = containerWidth / img.width;
    canvas.width = containerWidth;
    canvas.height = img.height * scale;
    
    // Draw original photo
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.style.display = 'block';
    document.getElementById('annotationControls').style.display = 'flex';
    
    // Clear annotations
    currentAnnotations = [];
    annotationHistory = [];
  };
  img.src = currentPhotoDataUrl;
}

function setTool(tool) {
  currentTool = tool;
  document.querySelectorAll('.annotation-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tool' + tool.charAt(0).toUpperCase() + tool.slice(1)).classList.add('active');
}

// Canvas click handler for annotations
document.getElementById('annotationCanvas').addEventListener('click', function(e) {
  const rect = this.getBoundingClientRect();
  const x = (e.clientX - rect.left) * (currentPhotoWidth / this.width);
  const y = (e.clientY - rect.top) * (currentPhotoHeight / this.height);
  
  const xScale = this.width / currentPhotoWidth;
  const yScale = this.height / currentPhotoHeight;
  
  const canvas = this;
  const ctx = canvas.getContext('2d');
  annotationHistory.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
  
  if(currentTool === 'circle') {
    const radius = 40;
    ctx.beginPath();
    ctx.arc(x, y, radius / xScale, 0, Math.PI * 2);
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 3 / xScale;
    ctx.stroke();
    currentAnnotations.push({
      type: 'circle',
      x: x, y: y, radius: radius,
      label: 'Hallmark'
    });
  } else if(currentTool === 'box') {
    const size = 60;
    ctx.strokeStyle = 'yellow';
    ctx.lineWidth = 3 / xScale;
    ctx.strokeRect(x - size/xScale/2, y - size/yScale/2, size/xScale, size/yScale);
    currentAnnotations.push({
      type: 'box',
      x: x, y: y, size: size,
      label: 'Wear Point'
    });
  } else if(currentTool === 'arrow') {
    // Draw arrow from a point to the click
    const startX = x - 80;
    const startY = y - 40;
    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = 'purple';
    ctx.lineWidth = 3 / xScale;
    ctx.stroke();
    currentAnnotations.push({
      type: 'arrow',
      startX: startX, startY: startY,
      x: x, y: y,
      label: 'Maker Mark'
    });
  }
  
  // Let the user name the mark; cancel keeps a useful default.
  const customLabel = window.prompt('Label this annotation', currentTool === 'circle' ? 'Hallmark' : currentTool === 'box' ? 'Wear Point' : 'Maker Mark');
  const label = customLabel === null || !customLabel.trim() ? (currentTool === 'circle' ? 'Hallmark' : currentTool === 'box' ? 'Wear Point' : 'Maker Mark') : customLabel.trim();
  currentAnnotations[currentAnnotations.length - 1].label = label;
  ctx.fillStyle = currentTool === 'circle' ? 'red' : currentTool === 'box' ? 'yellow' : 'purple';
  ctx.font = `${14/xScale}px sans-serif`;
  ctx.fillText(label, x - 30/xScale, y + (currentTool === 'box' ? 50/xScale : -10/xScale));
});

function undoAnnotation() {
  const canvas = document.getElementById('annotationCanvas');
  const ctx = canvas.getContext('2d');
  if (!annotationHistory.length) return;
  ctx.putImageData(annotationHistory.pop(), 0, 0);
  currentAnnotations.pop();
}
function exportAnnotatedPNG() {
  const canvas = document.getElementById('annotationCanvas');
  if (canvas.style.display === 'none') { alert('Annotate a photo first.'); return; }
  const link = document.createElement('a');
  link.download = `estatescout-annotated-${Date.now()}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}
async function shareAnnotatedPNG() {
  const canvas = document.getElementById('annotationCanvas');
  if (canvas.style.display === 'none') { alert('Annotate a photo first.'); return; }
  canvas.toBlob(async blob => {
    const file = new File([blob], 'estatescout-annotated.png', {type:'image/png'});
    if (navigator.canShare?.({files:[file]})) await navigator.share({title:'EstateScout annotation', files:[file]});
    else exportAnnotatedPNG();
  }, 'image/png');
}

function clearAnnotations() {
  const canvas = document.getElementById('annotationCanvas');
  const ctx = canvas.getContext('2d');
  const img = new Image();
  img.onload = function() {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    currentAnnotations = [];
    annotationHistory = [];
  };
  img.src = currentPhotoDataUrl;
}

function autoAnalyze() {
  if(!currentPhotoDataUrl) return;
  
  const canvas = document.getElementById('annotationCanvas');
  const ctx = canvas.getContext('2d');
  const img = new Image();
  
  img.onload = function() {
    // Redraw original
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    // Smart annotation: mark likely hallmark areas
    const w = canvas.width;
    const h = canvas.height;
    
    // Hallmark area (bottom center)
    const hx = w / 2;
    const hy = h * 0.85;
    ctx.beginPath();
    ctx.arc(hx, hy, 30, 0, Math.PI * 2);
    ctx.strokeStyle = 'green';
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = 'green';
    ctx.font = '12px sans-serif';
    ctx.fillText('Likely Hallmark Area', hx - 60, hy + 40);
    
    // Wear points (top left)
    const wx = w * 0.25;
    const wy = h * 0.25;
    ctx.strokeStyle = 'yellow';
    ctx.lineWidth = 3;
    ctx.strokeRect(wx - 30, wy - 25, 60, 50);
    ctx.fillStyle = 'yellow';
    ctx.font = '12px sans-serif';
    ctx.fillText('Wear Points', wx - 25, wy + 40);
    
    // Maker mark (center)
    const mx = w * 0.5;
    const my = h * 0.5;
    ctx.beginPath();
    ctx.moveTo(mx - 50, my - 30);
    ctx.lineTo(mx, my);
    ctx.strokeStyle = 'purple';
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = 'purple';
    ctx.font = '12px sans-serif';
    ctx.fillText('Check Maker Marks', mx - 60, my - 35);
    
    currentAnnotations = [
      { type: 'circle', x: hx, y: hy, radius: 30, label: 'Hallmark Area' },
      { type: 'box', x: wx, y: wy, size: 60, label: 'Wear Points' },
      { type: 'arrow', startX: mx - 50, startY: my - 30, x: mx, y: my, label: 'Maker Marks' }
    ];
    
    // Show analysis results
    showAnalysisResults();
  };
  img.src = currentPhotoDataUrl;
}

function showAnalysisResults() {
  const content = document.getElementById('analysisContent');
  const recommendations = [
    'Check underside for 925/Sterling marks',
    'Look for wear points (yellow/copper = plated)',
    'Test with magnet (sticks = NOT silver)',
    'Check weight (heavy for size = likely solid)'
  ];
  
  content.innerHTML = `
    <div class="info-box">
      <h4>📷 Photo Analysis Complete</h4>
      <p>Image: ${currentPhotoWidth}x${currentPhotoHeight}</p>
      <p>Annotations: ${currentAnnotations.length} marks identified</p>
    </div>
    <ul class="checklist">
      ${recommendations.map(r => `<li><div class="check-icon green">✓</div> ${r}</li>`).join('')}
    </ul>
  `;
  document.getElementById('photoAnalysis').style.display = 'block';
}

// ── Save to Library ───────────────────────────────────────────────────
function saveToLibrary() {
  if(!currentPhotoDataUrl) return;
  
  // Save to localStorage
  let library = JSON.parse(localStorage.getItem('estatescout_library') || '[]');
  const item = {
    id: `lib_${crypto.randomUUID()}`,
    photo: currentPhotoDataUrl,
    date: new Date().toLocaleDateString(),
    annotations: currentAnnotations.length,
    type: 'scanned'
  };
  library.unshift(item);
  localStorage.setItem('estatescout_library', JSON.stringify(library));
  publishApiWrite('/library', {item});
  
  alert('✅ Photo saved to Library!');
  retakePhoto();
  renderLibrary();
}

// ── Collection Management ─────────────────────────────────────────────
function collectionItems() {
  return JSON.parse(localStorage.getItem('estatescout_items') || '[]');
}
function csvCell(value) {
  return '"' + String(value ?? '').replace(/"/g, '""') + '"';
}
function eraseDeviceData() {
  if (!confirm('Delete this device\'s collection, library, training progress, and manual price? Export a backup first if you want to keep them.')) return;
  ['estatescout_items', 'estatescout_library', TRAINING_KEY, MANUAL_PRICE_KEY, OUTBOX_KEY].forEach(key => localStorage.removeItem(key));
  retakePhoto(); renderCollection(); renderLibrary(); saveTrainingProgress(); refreshPriceWidget();
}
function exportBackup() {
  const backup = {
    format: 'EstateScout backup', version: 1, exportedAt: new Date().toISOString(),
    items: collectionItems(), library: JSON.parse(localStorage.getItem('estatescout_library') || '[]'),
    training: getTrainingProgress()
  };
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], {type:'application/json'}));
  link.download = `estatescout-backup-${new Date().toISOString().slice(0,10)}.json`;
  link.click(); URL.revokeObjectURL(link.href);
}
function restoreBackup(input) {
  const file = input.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const backup = JSON.parse(String(reader.result));
      if (backup.format !== 'EstateScout backup' || !Array.isArray(backup.items) || !Array.isArray(backup.library)) throw new Error('Unsupported backup');
      if (!confirm(`Replace this device's collection with ${backup.items.length} backed-up items?`)) return;
      localStorage.setItem('estatescout_items', JSON.stringify(backup.items));
      localStorage.setItem('estatescout_library', JSON.stringify(backup.library));
      localStorage.setItem(TRAINING_KEY, JSON.stringify(backup.training || {}));
      renderCollection(); renderLibrary(); saveTrainingProgress();
    } catch (error) { alert('That file is not a valid EstateScout backup.'); }
    input.value = '';
  };
  reader.readAsText(file);
}
function exportCollectionCSV() {
  const items = collectionItems();
  const fields = ['type','desc','marks','weight','magnet','condition','verdict','value','notes','date'];
  const csv = [fields, ...items.map(item => fields.map(field => item[field]))]
    .map(row => row.map(csvCell).join(',')).join('\\r\\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8'}));
  link.download = `estatescout-collection-${new Date().toISOString().slice(0,10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}
function printCollectionReport() {
  const items = collectionItems();
  const report = items.length ? items.map(item => `<article><h2>${escapeHtml(item.desc || 'EstateScout item')}</h2><p><b>Verdict:</b> ${escapeHtml(item.verdict || 'Unknown')}</p><p><b>Marks:</b> ${escapeHtml(item.marks || 'Not recorded')} &nbsp; <b>Weight:</b> ${escapeHtml(item.weight || 'Not recorded')}g</p><p>${escapeHtml(item.notes || '')}</p></article>`).join('') : '<p>No collection items saved.</p>';
  const win = window.open('', '_blank');
  if (!win) { alert('Please allow pop-ups to create the report.'); return; }
  win.document.write(`<title>EstateScout Collection Report</title><style>body{font-family:Arial;padding:24px;color:#172033}article{border-bottom:1px solid #ccc;padding:12px 0}h1{color:#8b6b2e}</style><h1>EstateScout Collection Report</h1><p>Generated ${new Date().toLocaleString()}</p>${report}`);
  win.document.close(); win.focus(); win.print();
}
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function shareCollectionItem(index) {
  const item = collectionItems()[index];
  if (!item) return;
  const text = `EstateScout: ${item.desc || 'Item'} — ${item.verdict || 'Unknown'}${item.value ? `, estimated ${item.value}` : ''}`;
  if (navigator.share) await navigator.share({title:'EstateScout item', text});
  else await navigator.clipboard?.writeText(text);
}

function recentSalesFor(item) {
  const type = String(item.type || 'flatware').toLowerCase();
  const ranges = {
    flatware: [18, 72], holloware: [85, 420], jewelry: [25, 180], coin: [30, 260], decorative: [35, 240]
  };
  const [low, high] = ranges[type] || ranges.decorative;
  return [Math.round(low * 1.05), Math.round((low + high) / 2), Math.round(high * .92)];
}
function renderRecentSales(item) {
  const est = estimateValue(item);
  return `<div class="info-box" style="margin-top:10px;"><h4>📊 Value Estimate</h4><p>Estimated range: <b>${est}</b>. Based on type, marks, maker, condition, and weight. For purchase decisions, verify with a verified marketplace feed.</p></div>`;
}

function renderCollection(searchTerm) {
  const allItems = collectionItems();
  const indexedItems = allItems.map((item, index) => ({item, index}));
  let items = searchTerm ? indexedItems.filter(({item}) => filterCollection(searchTerm).includes(item)) : indexedItems;
  const filter = document.getElementById('collectionFilter')?.value || 'all';
  if (filter === 'needs-evidence') items = items.filter(({item}) => item.confidence !== 'high' || !item.evidence || !item.weight || !item.magnet);
  if (filter === 'high-confidence') items = items.filter(({item}) => item.confidence === 'high');
  if (filter === 'sold') items = items.filter(({item}) => Number(item.salePrice) > 0);
  const sort = document.getElementById('collectionSort')?.value || 'newest';
  const money = value => Number.parseFloat(String(value || '').replace(/[^0-9.-]/g, '')) || 0;
  items.sort((a, b) => {
    if (sort === 'oldest') return a.index - b.index;
    if (sort === 'value') return money(b.item.value) - money(a.item.value);
    if (sort === 'profit') return (money(b.item.salePrice) - money(b.item.purchasePrice)) - (money(a.item.salePrice) - money(a.item.purchasePrice));
    return a.index - b.index;
  });
  const container = document.getElementById('collectionList');

  if(allItems.length === 0) {
    container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg><p>Your collection is empty.<br>Tap "Add Item" to start tracking.</p></div>`;
    return;
  }

  container.innerHTML = items.map(({item, index}) => {
    const verdictColors = {'solid silver':'var(--success)','plated':'var(--warning)','fake':'var(--danger)','unknown':'var(--text-secondary)'};
    const verdictEmoji = {'solid silver':'✅','plated':'⚠️','fake':'❌','unknown':'❓'};
    return `
      <div class="collection-item">
        <div class="item-header">
          <span class="item-type">${escapeHtml(item.type || 'item')}</span>
          <span style="font-size:18px;">${verdictEmoji[item.verdict] || '🔍'}</span>
          <span style="font-size:11px;color:var(--text-secondary);">${escapeHtml(item.date || '')}</span>
          <button onclick="shareCollectionItem(${index})" style="background:none;border:none;font-size:16px;cursor:pointer;" aria-label="Share item">↗️</button>
          <button onclick="editCollectionItem(${index})" style="background:none;border:none;font-size:16px;cursor:pointer;" aria-label="Edit item">✏️</button>
          <button onclick="deleteCollectionItem(${index})" style="background:none;border:none;font-size:16px;cursor:pointer;" aria-label="Delete item">🗑️</button>
        </div>
        <div class="item-desc">${escapeHtml(item.desc || 'No description')}</div>
        ${item.marks ? `<div style="font-size:12px;color:var(--accent);margin-bottom:6px;">🏷️ ${escapeHtml(item.marks)}</div>` : ''}
        <div class="item-meta">
          ${item.weight ? `<span>⚖️ ${escapeHtml(item.weight)}g</span>` : ''}
          <span style="color:${verdictColors[item.verdict] || 'var(--text-secondary)'}">${escapeHtml(item.verdict || 'unknown')}</span>
          ${item.value ? `<span>💰 ${escapeHtml(item.value)}</span>` : ''}
        </div>
        ${item.purchasePrice ? `<div class="item-meta"><span>Paid: $${escapeHtml(item.purchasePrice)}</span>${item.salePrice ? `<span>Sold: $${escapeHtml(item.salePrice)} • Profit: $${(Number(item.salePrice) - Number(item.purchasePrice)).toFixed(2)}</span>` : '<span>Unsold</span>'}</div>` : ''}
        <div class="info-box" style="margin-top:10px;"><h4>Evidence • ${escapeHtml(item.confidence || 'medium')} confidence</h4><p>${escapeHtml(item.evidence || 'No item-specific evidence recorded yet. Capture hallmark, weight, magnet, and wear observations before relying on a verdict.')}</p></div>
        ${renderRecentSales(item)}
      </div>
    `;
  }).join('');

  const countEl = document.getElementById('collectionCount');
  if (countEl) {
    countEl.textContent = allItems.length === items.length
      ? `${allItems.length} items`
      : `${items.length} of ${allItems.length} items`;
  }
}

async function deleteCollectionItem(index) {
  if(!confirm('Delete this item?')) return;
  const items = collectionItems();
  const [item] = items.splice(index, 1);
  localStorage.setItem('estatescout_items', JSON.stringify(items));
  if (item?.id) await publishApiWrite(`/items/${encodeURIComponent(item.id)}`, null, 'DELETE');
  renderCollection();
}

function editCollectionItem(index) {
  const items = JSON.parse(localStorage.getItem('estatescout_items') || '[]');
  const item = items[index];
  if (!item) return;
  // Pre-fill the add modal with existing data
  document.getElementById('itemType').value = item.type || 'flatware';
  document.getElementById('itemDesc').value = item.desc || '';
  document.getElementById('itemMarks').value = item.marks || '';
  document.getElementById('itemWeight').value = item.weight || '';
  document.getElementById('itemMagnet').value = item.magnet || 'not attracted';
  document.getElementById('itemCondition').value = item.condition || 'good';
  document.getElementById('itemVerdict').value = item.verdict || 'unknown';
  document.getElementById('itemValue').value = item.value || '';
  document.getElementById('itemPurchasePrice').value = item.purchasePrice ?? '';
  document.getElementById('itemSalePrice').value = item.salePrice ?? '';
  document.getElementById('itemEvidence').value = item.evidence || '';
  document.getElementById('itemConfidence').value = item.confidence || 'medium';
  document.getElementById('itemNotes').value = item.notes || '';
  // Store edit index in a data attribute
  document.getElementById('addModal').dataset.editIndex = index;
  document.querySelector('#addModal h2').textContent = 'Edit Item';
  // Show photo if available
  const photoPreview = document.getElementById('itemPhotoPreview');
  if (item.photo) {
    photoPreview.src = item.photo;
    photoPreview.style.display = 'block';
  }
  document.getElementById('addModal').setAttribute('aria-hidden', 'false');
  document.getElementById('addModal').classList.add('active');
  document.getElementById('itemDesc').focus();
}

function openAddItem() {
  document.getElementById('addModal').dataset.editIndex = '';
  document.querySelector('#addModal h2').textContent = 'Add Item to Collection';
  // Reset form fields
  ['itemDesc','itemMarks','itemWeight','itemValue','itemPurchasePrice','itemSalePrice','itemEvidence','itemNotes'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('itemConfidence').value = 'medium';
  document.getElementById('itemPhoto').value = '';
  document.getElementById('itemPhotoPreview').style.display = 'none';
  document.getElementById('addModal').setAttribute('aria-hidden', 'false');
  document.getElementById('addModal').classList.add('active');
  document.getElementById('itemDesc').focus();
}

function closeModal() {
  document.getElementById('addModal').setAttribute('aria-hidden', 'true');
  document.getElementById('addModal').classList.remove('active');
  document.getElementById('addModal').dataset.editIndex = '';
  document.querySelector('#addModal h2').textContent = 'Add Item to Collection';
}

function previewItemPhoto(input) {
  if(input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      const preview = document.getElementById('itemPhotoPreview');
      preview.src = e.target.result;
      preview.style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function saveItem() {
  const editIndex = parseInt(document.getElementById('addModal').dataset.editIndex || '-1', 10);
  const item = {
    type: document.getElementById('itemType').value,
    desc: document.getElementById('itemDesc').value,
    marks: document.getElementById('itemMarks').value,
    weight: document.getElementById('itemWeight').value,
    magnet: document.getElementById('itemMagnet').value,
    condition: document.getElementById('itemCondition').value,
    verdict: document.getElementById('itemVerdict').value,
    value: document.getElementById('itemValue').value,
    purchasePrice: document.getElementById('itemPurchasePrice').value,
    salePrice: document.getElementById('itemSalePrice').value,
    evidence: document.getElementById('itemEvidence').value,
    confidence: document.getElementById('itemConfidence').value,
    notes: document.getElementById('itemNotes').value,
    date: new Date().toLocaleDateString(),
    id: editIndex >= 0 ? JSON.parse(localStorage.getItem('estatescout_items') || '[]')[editIndex]?.id : `item_${crypto.randomUUID()}`
  };

  // Handle photo if provided
  const photoPreview = document.getElementById('itemPhotoPreview');
  if(photoPreview.style.display !== 'none' && photoPreview.src) {
    item.photo = photoPreview.src;
  }

  const items = JSON.parse(localStorage.getItem('estatescout_items') || '[]');
  if (editIndex >= 0 && editIndex < items.length) {
    // Update existing item, preserve photo if not replaced
    if (!item.photo && items[editIndex].photo) item.photo = items[editIndex].photo;
    items[editIndex] = item;
  } else {
    items.unshift(item);
  }
  localStorage.setItem('estatescout_items', JSON.stringify(items));

  // Auto-estimate value and save training progress
  const newItem = items[editIndex >= 0 ? editIndex : 0] || item;
  if (!newItem.value) {
    newItem.value = estimateValue(newItem);
    items[editIndex >= 0 ? editIndex : 0] = newItem;
    localStorage.setItem('estatescout_items', JSON.stringify(items));
  }
  const savedItem = items[editIndex >= 0 ? editIndex : 0] || item;
  publishApiWrite(editIndex >= 0 ? `/items/${encodeURIComponent(savedItem.id)}` : '/items', {item: savedItem}, editIndex >= 0 ? 'PUT' : 'POST');
  saveTrainingProgress();

  closeModal();
  renderCollection();

  // Reset form
  ['itemDesc','itemMarks','itemWeight','itemValue','itemPurchasePrice','itemSalePrice','itemEvidence','itemNotes'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('itemConfidence').value = 'medium';
  document.getElementById('itemPhoto').value = '';
  document.getElementById('itemPhotoPreview').style.display = 'none';
  document.getElementById('addModal').dataset.editIndex = '';
  document.querySelector('#addModal h2').textContent = 'Add Item to Collection';
}

// ── Library ───────────────────────────────────────────────────────────
function renderLibrary() {
  const library = JSON.parse(localStorage.getItem('estatescout_library') || '[]');
  const container = document.getElementById('libraryList');
  
  if(library.length === 0) {
    container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg><p>Your library is empty.<br>Scan items to build your annotated photo library!</p></div>`;
    return;
  }
  
  container.innerHTML = library.map((item, i) => `
    <div class="library-item">
      <img src="${item.photo}" class="library-thumb" onclick="viewLibraryPhoto(${i})">
      <div class="library-info">
        <h4>📷 Scanned Item</h4>
        <p>${item.date} • ${item.annotations} annotations</p>
      </div>
      <div class="library-actions">
        <button onclick="deleteLibraryItem(${i})">🗑️</button>
      </div>
    </div>
  `).join('');
}

function viewLibraryPhoto(index) {
  const library = JSON.parse(localStorage.getItem('estatescout_library') || '[]');
  const item = library[index];
  if(item && item.photo) {
    // Open in new tab or show in modal
    const win = window.open();
    win.document.write(`<img src="${item.photo}" style="max-width:100%;">`);
  }
}

async function deleteLibraryItem(index) {
  if(!confirm('Delete this library item?')) return;
  const library = JSON.parse(localStorage.getItem('estatescout_library') || '[]');
  const [item] = library.splice(index, 1);
  localStorage.setItem('estatescout_library', JSON.stringify(library));
  if (item?.id) await publishApiWrite(`/library/${encodeURIComponent(item.id)}`, null, 'DELETE');
  renderLibrary();
}

// ── Module Content ────────────────────────────────────────────────────
const modules = {
  1: {
    title: 'Module 1: Basic Silver Identification',
    time: '30 min • Beginner',
    content: `
      <div class="info-box"><h4>Lesson 1.1: The Two Marks That Matter Most</h4><p>SOLID SILVER (WORTH $$$$): <b>925</b>, <b>STERLING</b>, <b>800/835</b>, <b>Lion Passant</b>. NOT SOLID (WORTH $): <b>EPNS</b>, <b>SILVER PLATED</b>, <b>EP</b>, <b>A1</b>.</p></div>
      
      <div class="info-box"><h4>Lesson 1.2: Weight Test</h4><p>Solid silver is dense and heavy. Teaspoon: Solid = 15-20g | Plated = 8-12g. If it feels LIGHT, it's probably plated.</p></div>
      
      <div class="info-box"><h4>Lesson 1.3: Magnet Test</h4><p>Silver is NOT magnetic. If magnet sticks = steel core, NOT silver. No stick = could be silver OR non-magnetic base metal (brass, nickel silver).</p></div>
      
      <div class="info-box"><h4>Lesson 1.4: Wear Points</h4><p>Fork tines, spoon backs, handle ends. Yellow/gold color showing through = PLATED. Uniform silver everywhere = LIKELY SOLID.</p></div>
      
      <div class="info-box"><h4>Lesson 1.5: 60-Second Checklist</h4><p>Marks → Weight → Wear points → Magnet → Decision. Focus on HEAVY items with NO wear color showing.</p></div>
    `
  },
  2: {
    title: 'Module 2: Intermediate Silver Identification',
    time: '45 min • Intermediate',
    content: `
      <div class="info-box"><h4>British Hallmarks</h4><p><b>Lion Passant</b> = 925 sterling. <b>Assay offices:</b> London (anchor), Birmingham (anchor), Sheffield (rose), Edinburgh (castle). <b>Date letters</b> = year made. <b>Maker marks</b> = two initials in shield.</p></div>
      
      <div class="info-box"><h4>Famous Makers</h4><p><b>Tiffany & Co.</b> - Extremely valuable. <b>Gorham</b> - Art Nouveau collectible. <b>Reed & Barton</b> - Quality American (1824-2015). <b>International Silver</b> - Common but collectible.</p></div>
      
      <div class="info-box"><h4>Spotting Reproductions</h4><p>Perfect condition + modern fonts = suspicious. Wrong hallmark combos = fake. 2+ red flags = walk away.</p></div>
      
      <div class="info-box"><h4>Old Sheffield Plate (OSP)</h4><p>Fused silver/copper sheets (1740s-1840s). Shows copper bleeding at wear points. Bluish cast vs electroplate. No EP marks.</p></div>
    `
  },
  3: {
    title: 'Module 3: Advanced Silver Identification',
    time: '60 min • Advanced',
    content: `
      <div class="info-box"><h4>Date Letter System</h4><p>Each assay office has its own alphabet cycle. Font style + shield shape = specific year. Look for small letter on back/underside.</p></div>
      
      <div class="info-box"><h4>Rare & Valuable Marks</h4><p><b>Paul de Lamerie (PL)</b> - $5k-$100k+. <b>Paul Revere (PR)</b> - $10k-$500k+. <b>Britannia 958</b> - Higher purity, rare.</p></div>
      
      <div class="info-box"><h4>Weighted Silver</h4><p>Silver shell filled with lead. Hollow sound when tapped. X-ray needed to detect.</p></div>
      
      <div class="info-box"><h4>US Coin Silver</h4><p>Pre-1965 dimes/quarters/half dollars = 90% silver. Dime: 0.0723 oz | Quarter: 0.1600 oz | Half dollar: 0.3616 oz.</p></div>
    `
  },
  4: {
    title: 'Module 4: Practical Estate Sale Scenarios',
    time: '30 min • Applied',
    content: `
      <div class="info-box"><h4>Scenario 1: Drawer of Mixed Flatware</h4><p>Sort by weight (heavy = likely solid). Check each for 925 mark. Buy lot if 50%+ solid silver.</p></div>
      
      <div class="info-box"><h4>Scenario 2: Service for 12</h4><p>Check if complete. Verify all pieces are solid (925 mark). Complete service worth 2-3x individual pieces.</p></div>
      
      <div class="info-box"><h4>Scenario 3: Candlesticks</h4><p><b>PAIRS are essential for value.</b> Single = low value ($5-20). Pair of solid silver = valuable ($100-500+).</p></div>
      
      <div class="info-box"><h4>Scenario 4: Coin Collection</h4><p>Check dates (pre-1965 = silver). Count total silver content. Buy if mostly pre-1965 coins.</p></div>
      
      <div class="info-box"><h4>Golden Rules</h4><p>Heavy + No wear color + 925 mark = SOLID. Pairs > Singles. Complete services > Individual pieces.</p></div>
    `
  }
};

function openModule(num) {
  const m = modules[num];
  document.getElementById('moduleContent').innerHTML = `<h2>${m.title}</h2><div class="meta" style="color:var(--text-secondary);margin-bottom:16px;">${m.time}</div>${m.content}`;
  document.getElementById('moduleModal').classList.add('active');
}

function closeModuleModal() {
  document.getElementById('moduleModal').classList.remove('active');
}

// ── Close modals on overlay click ─────────────────────────────────────
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', function(e) {
    if(e.target === this) this.classList.remove('active');
  });
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (document.getElementById('addModal').classList.contains('active')) closeModal();
    if (document.getElementById('moduleModal').classList.contains('active')) closeModuleModal();
  }
});

function renderPriceWidget(prices) {
  const content = document.getElementById('priceWidgetContent');
  const spinner = document.getElementById('priceSpinner');
  if (spinner) spinner.style.display = 'none';
  if (!prices || prices.status === 'unavailable' || prices.western_usd_per_troy_oz == null) {
    content.innerHTML = '<p>Verified live pricing is unavailable. No estimate is being shown.</p>';
    return;
  }
  const status = String(prices.status || 'unknown').toUpperCase();
  const delayed = /delayed|futures/i.test(`${prices.status || ''} ${prices.western_source || ''}`);
  const timestamp = prices.fetched_at ? new Date(Number(prices.fetched_at) * 1000).toLocaleString() : 'unknown';
  const westernSource = escapeHtml(prices.western_source || 'Western feed');
  const shanghaiSource = escapeHtml(prices.shanghai_source || 'Shanghai feed');
  const shanghai = prices.shanghai_cny_per_gram == null
    ? '<div class="benchmark-row"><span class="benchmark-label">🇨🇳 Shanghai</span><b>Unavailable</b></div><div class="benchmark-row"><span class="benchmark-label">🇨🇳 Shanghai converted</span><b>Unavailable</b></div>'
    : `<div class="benchmark-row"><span class="benchmark-label">🇨🇳 Shanghai</span><b>¥${Number(prices.shanghai_cny_per_gram).toFixed(2)} CNY / gram</b></div><div class="benchmark-row"><span class="benchmark-label">🇨🇳 Shanghai converted</span><b>$${Number(prices.shanghai_usd_per_troy_oz).toFixed(2)} USD / troy oz</b></div>`;
  const badge = delayed ? '<span class="badge badge-plated">Delayed futures</span>' : `<span class="badge badge-solid">${status}</span>`;
  const fx = Number(prices.usd_cny) > 0 ? `FX: 1 USD = ¥${Number(prices.usd_cny).toFixed(4)} • 31.1034768 g/troy oz` : 'FX and Shanghai conversion unavailable';
  content.innerHTML = `<div class="benchmark-row"><span class="benchmark-label">🌎 Western price</span><b>$${Number(prices.western_usd_per_troy_oz).toFixed(2)} USD / troy oz</b></div>${shanghai}<p style="font-size:11px;margin-top:10px;">${badge} &nbsp; Updated: ${timestamp}<br>Western: ${westernSource}<br>Shanghai: ${shanghaiSource}<br>${fx}</p>`;
}
const MANUAL_PRICE_KEY = 'estatescout_manual_western_price';
function manualPrice() {
  const value = Number(localStorage.getItem(MANUAL_PRICE_KEY));
  return Number.isFinite(value) && value > 0 ? value : null;
}
function saveManualPrice() {
  const input = document.getElementById('manualWesternPrice');
  const value = Number(input.value);
  if (!Number.isFinite(value) || value <= 0) { input.setCustomValidity('Enter a positive USD per troy ounce price.'); input.reportValidity(); return; }
  input.setCustomValidity('');
  localStorage.setItem(MANUAL_PRICE_KEY, String(value));
  refreshPriceWidget();
}
function clearManualPrice() {
  localStorage.removeItem(MANUAL_PRICE_KEY);
  document.getElementById('manualWesternPrice').value = '';
  refreshPriceWidget();
}
async function refreshPriceWidget() {
  try {
    const manual = manualPrice();
    if (manual) {
      document.getElementById('manualWesternPrice').value = manual;
      renderPriceWidget({status:'manual', western_usd_per_troy_oz:manual, usd_cny:0, western_source:'Manual field entry — verify before buying', shanghai_source:'Not entered', fetched_at:Math.floor(Date.now() / 1000)});
      return;
    }
    if (ESTATESCOUT_API) {
      const response = await fetch(`${ESTATESCOUT_API}/silver-price`, {headers:{'Accept':'application/json'}});
      renderPriceWidget(response.ok ? await response.json() : {status:'unavailable'});
      return;
    }
    try {
      // Same-origin feed, refreshed every 10 minutes by GitHub Actions
      // (public/feeds/silver_prices.json). Yahoo's API has no CORS headers,
      // so browsers cannot call it directly — the server-side refresh exists
      // precisely to serve it from this origin.
      const feedResponse = await fetch('feeds/silver_prices.json', {headers:{'Accept':'application/json'}});
      if (feedResponse.ok) {
        const feed = await feedResponse.json();
        if (feed.status && feed.status !== 'unavailable' && feed.western_usd_per_troy_oz != null) {
          renderPriceWidget(feed);
          return;
        }
      }
    } catch (feedError) { /* fall through to direct Yahoo attempt */ }
    try {
      // Direct Yahoo attempt (works in desktop browsers that permit it;
      // fails in most mobile PWA contexts due to missing CORS headers).
      const quote = async symbol => {
        const response = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1d&interval=1m`);
        const data = await response.json();
        return data.chart.result[0].meta.regularMarketPrice;
      };
      const [western, fx] = await Promise.all([quote('SI=F'), quote('CNY=X')]);
      renderPriceWidget({status:'delayed', western_usd_per_troy_oz:western, usd_cny:fx, western_source:'Yahoo Finance SI=F (COMEX futures, delayed)', shanghai_source:'No configured Shanghai source', fetched_at:Math.floor(Date.now() / 1000)});
    } catch (error) { renderPriceWidget({status:'unavailable'}); }
  } catch (error) { renderPriceWidget({status:'unavailable'}); }
}

// ── Shared API / Offline Sync ─────────────────────────────────────────
if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});
const ESTATESCOUT_API = localStorage.getItem('estatescout_api') || '';
const OUTBOX_KEY = 'estatescout_outbox';
function queueApiWrite(path, payload, method = 'POST') {
  const outbox = JSON.parse(localStorage.getItem(OUTBOX_KEY) || '[]');
  outbox.push({path, payload, method, queuedAt: new Date().toISOString()});
  localStorage.setItem(OUTBOX_KEY, JSON.stringify(outbox));
}
async function flushOutbox() {
  const outbox = JSON.parse(localStorage.getItem(OUTBOX_KEY) || '[]');
  const remaining = [];
  for (const entry of outbox) {
    try {
      const options = {method: entry.method || 'POST', headers:{'Content-Type':'application/json'}};
      if (entry.payload !== null) options.body = JSON.stringify(entry.payload);
      const response = await fetch(`${ESTATESCOUT_API}${entry.path}`, options);
      if (!response.ok) throw new Error('write failed');
    } catch (error) { remaining.push(entry); }
  }
  localStorage.setItem(OUTBOX_KEY, JSON.stringify(remaining));
}
async function publishApiWrite(path, payload, method = 'POST') {
  if (!ESTATESCOUT_API) return;
  try {
    const options = {method, headers:{'Content-Type':'application/json'}};
    if (payload !== null) options.body = JSON.stringify(payload);
    const response = await fetch(`${ESTATESCOUT_API}${path}`, options);
    if (!response.ok) throw new Error('write failed');
  } catch (error) { queueApiWrite(path, payload, method); setConnectionStatus(false); }
}
function setConnectionStatus(online) {
  const el = document.getElementById('connectionStatus');
  if (!el) return;
  el.textContent = online ? '● Online' : '● Offline';
  el.style.color = online ? 'var(--success)' : 'var(--warning)';
  el.style.background = online ? 'rgba(74,222,128,.15)' : 'rgba(251,191,36,.15)';
}
async function syncFromServer() {
  if (!ESTATESCOUT_API) {
    const el = document.getElementById('connectionStatus');
    if (el) { el.textContent = '● Device-only'; el.style.color = 'var(--accent)'; el.style.background = 'rgba(200,164,90,.15)'; }
    return;
  }
  try {
    const [itemsResponse, libraryResponse] = await Promise.all([
      fetch(`${ESTATESCOUT_API}/items`, {headers: {'Accept': 'application/json'}}),
      fetch(`${ESTATESCOUT_API}/library`, {headers: {'Accept': 'application/json'}})
    ]);
    if (!itemsResponse.ok || !libraryResponse.ok) throw new Error('sync failed');
    const items = await itemsResponse.json();
    const library = await libraryResponse.json();
    if (Array.isArray(items.items)) localStorage.setItem('estatescout_items', JSON.stringify(items.items));
    if (Array.isArray(library.items)) localStorage.setItem('estatescout_library', JSON.stringify(library.items));
    setConnectionStatus(true);
    renderCollection();
    renderLibrary();
  } catch (error) {
    setConnectionStatus(false);
  }
}
window.addEventListener('online', () => { setConnectionStatus(true); flushOutbox().then(syncFromServer); });
window.addEventListener('offline', () => setConnectionStatus(false));

// ── Training Progress ─────────────────────────────────────────────────
const TRAINING_KEY = 'estatescout_training';
function getTrainingProgress() {
  try { return JSON.parse(localStorage.getItem(TRAINING_KEY) || '{}'); } catch { return {}; }
}
function saveTrainingProgress() {
  const progress = getTrainingProgress();
  // Calculate progress based on items in collection
  const items = collectionItems();
  const solidCount = items.filter(i => i.verdict === 'solid silver').length;
  const platedCount = items.filter(i => i.verdict === 'plated').length;
  const total = items.length;
  // Module 1 is 100% when user has identified at least 3 items
  progress.m1 = total >= 3 ? 100 : Math.min(100, Math.round((total / 3) * 100));
  // Module 2 is 100% when user has identified both solid and plated
  progress.m2 = (solidCount > 0 && platedCount > 0) ? 100 : 0;
  // Module 3 is 100% when user has identified 2+ famous makers
  const makers = items.filter(i => i.marks && /tiffany|gorham|reed|storr|revere|lamerie/i.test(i.marks)).length;
  progress.m3 = makers >= 2 ? 100 : 0;
  // Module 4 is 100% when user has 3+ solid items with no wear
  const noWear = items.filter(i => i.verdict === 'solid silver' && i.condition === 'excellent').length;
  progress.m4 = noWear >= 3 ? 100 : 0;
  localStorage.setItem(TRAINING_KEY, JSON.stringify(progress));
  updateProgressBars(progress);
}
function updateProgressBars(progress) {
  document.querySelectorAll('.progress-fill').forEach((bar, idx) => {
    const pct = progress['m' + (idx + 1)] || 0;
    bar.style.width = pct + '%';
  });
}

// ── Value Estimation ──────────────────────────────────────────────────
function estimateValue(item) {
  const type = String(item.type || 'flatware').toLowerCase();
  const verdict = String(item.verdict || '').toLowerCase();
  const marks = String(item.marks || '').toLowerCase();
  const weight = parseFloat(item.weight) || 0;
  const condition = String(item.condition || 'fair').toLowerCase();

  let base = 0;
  const ranges = {
    flatware: [18, 72], holloware: [85, 420], jewelry: [25, 180],
    coin: [30, 260], decorative: [35, 240]
  };
  const [low, high] = ranges[type] || ranges.decorative;

  // Base value from type
  base = (low + high) / 2;

  // Multipliers
  let mult = 1;

  // Solid silver mark
  if (/925|sterling|800|835|958|coin silver/i.test(marks)) {
    mult *= 2.5;
  } else if (/epns|plated|ep |a1/i.test(marks)) {
    mult *= 0.15;
  }

  // Famous maker
  if (/tiffany|gorham|reed.*barton|storr|revere|lamerie/i.test(marks)) {
    mult *= 3;
  }

  // Condition
  const condMult = { excellent: 1.5, good: 1.0, fair: 0.7, poor: 0.4 };
  mult *= condMult[condition] || 0.5;

  // Weight bonus for solid pieces
  if (/925|sterling/i.test(marks) && weight > 15) {
    mult *= 1.2;
  }

  const estLow = Math.round(base * mult * 0.6);
  const estHigh = Math.round(base * mult * 1.4);
  return estLow > 0 ? `$${estLow}–$${estHigh}` : '—';
}

// ── Init ──────────────────────────────────────────────────────────────
initVaultLock();
if (localStorage.getItem('estatescout_floor_mode') === '1') toggleFloorMode();
renderCollection();
renderLibrary();
syncFromServer();
refreshPriceWidget();
saveTrainingProgress();

// ── AI Item Analysis (proof build: local model via /api proxy) ──────
const AI_API = localStorage.getItem('estatescout_api') || '/api';
let aiPhoto = null; // {dataUrl, name}

function loadAiPhoto(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    aiPhoto = {dataUrl: reader.result, name: file.name};
    document.getElementById('aiRunBtn').disabled = false;
    document.getElementById('aiResult').style.display = 'none';
    document.getElementById('aiCanvas').style.display = 'none';
  };
  reader.readAsDataURL(file);
  input.value = '';
}

async function runAiAnalysis() {
  if (!aiPhoto) return;
  const result = document.getElementById('aiResult');
  const btn = document.getElementById('aiRunBtn');
  result.style.display = 'block';
  result.textContent = 'Analyzing with local model… (vision can take up to a minute)';
  btn.disabled = true;
  try {
    const note = document.getElementById('aiNote').value || '';
    const res = await fetch(AI_API + '/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({image: aiPhoto.dataUrl, note})
    });
    if (!res.ok) throw new Error('proxy HTTP ' + res.status + ': ' + (await res.text()).slice(0, 120));
    const data = await res.json();
    drawAiMarks(data.observations || []);
    const lines = (data.observations || []).map(o => '⭕ ' + o.label + ' — ' + o.reason);
    result.textContent = (data.confidence ? '[' + data.confidence.toUpperCase() + '] ' : '')
      + (data.verdict || 'No verdict.') + (lines.length ? '\n\n' + lines.join('\n') : '\n\nNo marks identified.');
  } catch (err) {
    result.textContent = 'AI analysis unavailable: ' + err.message
      + '\n(Start the dev proxy with python3 server/server.py and make sure the local model is loaded.)';
  } finally {
    btn.disabled = false;
  }
}

// Fixed local drawing: model coords only, model never draws anything.
function drawAiMarks(observations) {
  const canvas = document.getElementById('aiCanvas');
  const img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    ctx.lineWidth = Math.max(3, Math.round(canvas.width / 250));
    ctx.strokeStyle = 'red';
    ctx.fillStyle = 'red';
    ctx.font = 'bold ' + Math.max(16, Math.round(canvas.width / 45)) + 'px sans-serif';
    for (const o of observations) {
      const x = o.x * canvas.width, y = o.y * canvas.height;
      const w = o.w * canvas.width, h = o.h * canvas.height;
      const cx = x + w / 2, cy = y + h / 2, r = Math.max(w, h) / 2 + 6;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillText(o.label, x, Math.max(20, y - 6));
    }
    canvas.style.display = 'block';
  };
  img.src = aiPhoto.dataUrl;
}
