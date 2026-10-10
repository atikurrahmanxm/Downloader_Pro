// ==========================================================================
// Downloader Pro - Frontend Application Engine
// ==========================================================================

// Application State
let detectedVideos = [];
let pollInterval = null;
let currentPreviewItem = null;

// DOM Elements
const scanForm = document.getElementById('scanForm');
const urlInput = document.getElementById('urlInput');
const clearInputBtn = document.getElementById('clearInputBtn');
const scanBtn = document.getElementById('scanBtn');
const scanLoading = document.getElementById('scanLoading');
const resultsSection = document.getElementById('resultsSection');
const resultsCount = document.getElementById('resultsCount');
const resultsUrl = document.getElementById('resultsUrl');
const videoCardsGrid = document.getElementById('videoCardsGrid');
const selectAllCheckbox = document.getElementById('selectAllCheckbox');
const selectedCount = document.getElementById('selectedCount');
const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
const downloadAllBtn = document.getElementById('downloadAllBtn');
const openFolderBtn = document.getElementById('openFolderBtn');
const activeCountBadge = document.getElementById('activeCountBadge');
const tasksList = document.getElementById('tasksList');
const emptyTasksNotice = document.getElementById('emptyTasksNotice');
const clearCompletedBtn = document.getElementById('clearCompletedBtn');
const pasteBtn = document.getElementById('pasteBtn');

// Modal Elements
const previewModal = document.getElementById('previewModal');
const previewTitle = document.getElementById('previewTitle');
const modalVideoPlayer = document.getElementById('modalVideoPlayer');
const previewQuality = document.getElementById('previewQuality');
const previewDownloadBtn = document.getElementById('previewDownloadBtn');
const closePreviewBtn = document.getElementById('closePreviewBtn');

// Toast Notification
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast pointer-events-auto flex items-center space-x-2.5 px-4 py-3 rounded-xl shadow-2xl text-xs sm:text-sm font-semibold border backdrop-blur-xl ${
        type === 'success' 
            ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/30' 
            : type === 'error'
            ? 'bg-rose-950/90 text-rose-200 border-rose-500/30'
            : 'bg-slate-900/90 text-slate-200 border-slate-700/60'
    }`;
    
    const icon = type === 'success' ? 'fa-circle-check text-emerald-400' 
               : type === 'error' ? 'fa-triangle-exclamation text-rose-400' 
               : 'fa-circle-info text-indigo-400';

    toast.innerHTML = `<i class="fa-solid ${icon} text-base"></i><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Escape HTML utility
function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Input Clear Button Listener
urlInput.addEventListener('input', () => {
    if (urlInput.value.trim().length > 0) {
        clearInputBtn.classList.remove('hidden');
    } else {
        clearInputBtn.classList.add('hidden');
    }
});

clearInputBtn.addEventListener('click', () => {
    urlInput.value = '';
    clearInputBtn.classList.add('hidden');
    urlInput.focus();
});

// Clipboard Paste
pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            urlInput.value = text.trim();
            clearInputBtn.classList.remove('hidden');
            showToast('URL pasted from clipboard!', 'info');
        }
    } catch (e) {
        urlInput.focus();
    }
});

// Quick Example Buttons
document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        urlInput.value = btn.dataset.url;
        clearInputBtn.classList.remove('hidden');
        scanForm.dispatchEvent(new Event('submit'));
    });
});

// Scan Form Submission
scanForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    scanBtn.disabled = true;
    scanBtn.classList.add('opacity-75');
    scanLoading.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    videoCardsGrid.innerHTML = '';
    detectedVideos = [];

    try {
        const resp = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await resp.json();

        if (data.success && data.videos && data.videos.length > 0) {
            detectedVideos = data.videos;
            renderVideoCards(data.videos, data.url);
            showToast(`Found ${data.videos.length} video(s)!`, 'success');
        } else if (data.success && (!data.videos || data.videos.length === 0)) {
            showToast('No downloadable video streams could be found on this page.', 'error');
        } else {
            showToast(data.error || 'Failed to scan page.', 'error');
        }
    } catch (err) {
        showToast('Connection error while contacting server.', 'error');
    } finally {
        scanBtn.disabled = false;
        scanBtn.classList.remove('opacity-75');
        scanLoading.classList.add('hidden');
    }
});

// Determine badge based on quality string or height
function getQualityBadge(formats) {
    if (!formats || formats.length === 0) return { label: 'HD', class: 'bg-indigo-600/90 text-white' };
    const maxFormat = formats[0];
    const q = (maxFormat.quality || '').toLowerCase();
    const h = maxFormat.height || 0;

    if (h >= 2160 || q.includes('4k') || q.includes('2160')) {
        return { label: '4K UHD', class: 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-sm' };
    }
    if (h >= 1440 || q.includes('1440') || q.includes('2k')) {
        return { label: '2K QHD', class: 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white' };
    }
    if (h >= 1080 || q.includes('1080')) {
        return { label: '1080p FHD', class: 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white' };
    }
    if (h >= 720 || q.includes('720')) {
        return { label: '720p HD', class: 'bg-gradient-to-r from-teal-600 to-cyan-600 text-white' };
    }
    return { label: 'HD Stream', class: 'bg-slate-700/90 text-slate-200' };
}

// Render Video Cards
function renderVideoCards(videos, currentUrl) {
    resultsCount.textContent = videos.length;
    resultsUrl.textContent = currentUrl;
    videoCardsGrid.innerHTML = '';
    selectAllCheckbox.checked = false;
    updateSelectedCount();

    videos.forEach((video, index) => {
        const card = document.createElement('div');
        card.className = 'video-card group relative bg-[#0f172a]/90 border border-slate-800/90 rounded-2xl overflow-hidden flex flex-col justify-between shadow-xl';
        card.dataset.index = index;

        const defaultPoster = video.poster || '';
        const posterImgHtml = defaultPoster 
            ? `<img src="${escapeHtml(defaultPoster)}" alt="${escapeHtml(video.title)}" class="w-full h-full object-cover transition duration-300 group-hover:scale-105" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\'w-full h-full flex items-center justify-center bg-slate-900\'><i class=\'fa-solid fa-film text-3xl text-slate-700\'></i></div>'">`
            : `<div class="w-full h-full flex items-center justify-center bg-slate-900"><i class="fa-solid fa-film text-3xl text-slate-700"></i></div>`;

        let formatOptions = '';
        if (video.formats && video.formats.length > 0) {
            video.formats.forEach((fmt) => {
                formatOptions += `<option value="${escapeHtml(fmt.url)}">${escapeHtml(fmt.quality || 'Video')}</option>`;
            });
        } else {
            formatOptions = `<option value="${escapeHtml(video.default_url)}">Original Best Quality</option>`;
        }

        const badge = getQualityBadge(video.formats);

        card.innerHTML = `
            <div>
                <!-- Thumbnail & Media Details -->
                <div class="relative aspect-video bg-black/60 overflow-hidden">
                    ${posterImgHtml}
                    
                    <!-- Checkbox -->
                    <div class="absolute top-2.5 left-2.5 z-10">
                        <input type="checkbox" class="video-checkbox w-4 h-4 rounded border-slate-600 bg-slate-900/80 text-indigo-600 focus:ring-indigo-500 cursor-pointer" data-index="${index}">
                    </div>

                    <!-- Quality Badge -->
                    <div class="absolute top-2.5 right-2.5 z-10 px-2 py-0.5 rounded-full text-[10px] font-extrabold ${badge.class}">
                        ${badge.label}
                    </div>

                    <!-- Duration Badge -->
                    ${video.duration_formatted ? `
                        <div class="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[11px] font-mono font-semibold text-white border border-white/10">
                            ${escapeHtml(video.duration_formatted)}
                        </div>
                    ` : ''}

                    <!-- Source Type Tag -->
                    <div class="absolute bottom-2.5 left-2.5 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-900/85 backdrop-blur-md text-slate-300 border border-slate-700/60 max-w-[130px] truncate">
                        ${escapeHtml(video.source_type)}
                    </div>

                    <!-- Center Play Button Overlay -->
                    <button class="preview-btn absolute inset-0 m-auto w-12 h-12 rounded-full bg-indigo-600/90 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200 transform scale-90 group-hover:scale-100 hover:bg-indigo-500 shadow-2xl" data-index="${index}" title="Preview Video">
                        <i class="fa-solid fa-play ml-0.5 text-base"></i>
                    </button>
                </div>

                <!-- Video Title & Format Selector -->
                <div class="p-4 space-y-3">
                    <h4 class="text-xs sm:text-sm font-bold text-white line-clamp-2 leading-snug group-hover:text-indigo-200 transition" title="${escapeHtml(video.title)}">
                        ${escapeHtml(video.title)}
                    </h4>

                    <div class="space-y-1">
                        <div class="flex items-center justify-between text-[11px] text-slate-400">
                            <span>Format / Quality:</span>
                        </div>
                        <select class="quality-select w-full bg-[#080c16] border border-slate-700/80 text-slate-200 text-xs rounded-xl px-2.5 py-2 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500" data-index="${index}">
                            ${formatOptions}
                        </select>
                    </div>
                </div>
            </div>

            <!-- Card Bottom Action Buttons -->
            <div class="p-4 pt-0 grid grid-cols-2 gap-2">
                <button class="preview-btn-bottom flex items-center justify-center space-x-1.5 text-xs font-semibold text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/60 py-2.5 rounded-xl transition active:scale-95" data-index="${index}">
                    <i class="fa-solid fa-eye text-slate-400"></i>
                    <span>Preview</span>
                </button>
                <button class="download-card-btn flex items-center justify-center space-x-1.5 text-xs font-semibold bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white py-2.5 rounded-xl transition shadow-lg shadow-indigo-600/25 active:scale-95" data-index="${index}">
                    <i class="fa-solid fa-download"></i>
                    <span>Download</span>
                </button>
            </div>
        `;

        videoCardsGrid.appendChild(card);
    });

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Checkboxes Selection Logic
videoCardsGrid.addEventListener('change', (e) => {
    if (e.target.classList.contains('video-checkbox')) {
        updateSelectedCount();
    }
});

selectAllCheckbox.addEventListener('change', () => {
    const checked = selectAllCheckbox.checked;
    document.querySelectorAll('.video-checkbox').forEach(cb => {
        cb.checked = checked;
    });
    updateSelectedCount();
});

function updateSelectedCount() {
    const selected = document.querySelectorAll('.video-checkbox:checked').length;
    selectedCount.textContent = selected;
    downloadSelectedBtn.disabled = selected === 0;
}

// Card Click Event Delegation
videoCardsGrid.addEventListener('click', (e) => {
    const previewTrigger = e.target.closest('.preview-btn') || e.target.closest('.preview-btn-bottom');
    if (previewTrigger) {
        const index = parseInt(previewTrigger.dataset.index);
        openPreview(index);
        return;
    }

    const downloadTrigger = e.target.closest('.download-card-btn');
    if (downloadTrigger) {
        const index = parseInt(downloadTrigger.dataset.index);
        downloadCard(index);
        return;
    }
});

// Single Download Execution
async function downloadCard(index) {
    const video = detectedVideos[index];
    if (!video) return;

    const card = document.querySelector(`.video-card[data-index="${index}"]`);
    const select = card.querySelector('.quality-select');
    const selectedUrl = select.value || video.default_url;
    const selectedQuality = select.options[select.selectedIndex]?.text || "Best";

    try {
        const resp = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: video.title,
                url: selectedUrl,
                quality: selectedQuality,
                poster: video.poster,
                page_url: video.page_url || "",
                use_ytdlp: video.use_ytdlp || false
            })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Downloading: "${video.title}"`, 'success');
            pollTasks();
        } else {
            showToast(data.error || 'Download failed to start.', 'error');
        }
    } catch (e) {
        showToast('Error sending download request.', 'error');
    }
}

// Batch Selected Download
downloadSelectedBtn.addEventListener('click', async () => {
    const selectedBoxes = document.querySelectorAll('.video-checkbox:checked');
    const items = [];

    selectedBoxes.forEach(cb => {
        const index = parseInt(cb.dataset.index);
        const video = detectedVideos[index];
        if (video) {
            const card = document.querySelector(`.video-card[data-index="${index}"]`);
            const select = card.querySelector('.quality-select');
            items.push({
                title: video.title,
                url: select.value || video.default_url,
                quality: select.options[select.selectedIndex]?.text || "Best",
                poster: video.poster,
                page_url: video.page_url || "",
                use_ytdlp: video.use_ytdlp || false
            });
        }
    });

    if (items.length === 0) return;

    try {
        const resp = await fetch('/api/download-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Queued ${data.queued} video(s) for download!`, 'success');
            pollTasks();
        }
    } catch (e) {
        showToast('Batch download request failed.', 'error');
    }
});

// Download All
downloadAllBtn.addEventListener('click', async () => {
    if (detectedVideos.length === 0) return;

    const items = detectedVideos.map((video, index) => {
        const card = document.querySelector(`.video-card[data-index="${index}"]`);
        const select = card ? card.querySelector('.quality-select') : null;
        return {
            title: video.title,
            url: select ? select.value : video.default_url,
            quality: select ? select.options[select.selectedIndex]?.text : "Best",
            poster: video.poster,
            page_url: video.page_url || "",
            use_ytdlp: video.use_ytdlp || false
        };
    });

    try {
        const resp = await fetch('/api/download-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Queued all ${data.queued} video(s) for download!`, 'success');
            pollTasks();
        }
    } catch (e) {
        showToast('Failed to queue all videos.', 'error');
    }
});

// Video Preview Handlers
function openPreview(index) {
    const video = detectedVideos[index];
    if (!video) return;

    const card = document.querySelector(`.video-card[data-index="${index}"]`);
    const select = card.querySelector('.quality-select');
    const selectedUrl = select.value || video.default_url;
    const selectedQuality = select.options[select.selectedIndex]?.text || "Preview";

    currentPreviewItem = { video, selectedUrl, selectedQuality };

    previewTitle.textContent = video.title;
    previewQuality.textContent = `Quality: ${selectedQuality}`;
    modalVideoPlayer.src = selectedUrl;
    previewModal.classList.remove('hidden');
    modalVideoPlayer.play().catch(() => {});
}

closePreviewBtn.addEventListener('click', closePreview);
previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) closePreview();
});

function closePreview() {
    modalVideoPlayer.pause();
    modalVideoPlayer.src = '';
    previewModal.classList.add('hidden');
    currentPreviewItem = null;
}

previewDownloadBtn.addEventListener('click', () => {
    if (currentPreviewItem) {
        const { video, selectedUrl, selectedQuality } = currentPreviewItem;
        fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: video.title,
                url: selectedUrl,
                quality: selectedQuality,
                poster: video.poster,
                page_url: video.page_url || "",
                use_ytdlp: video.use_ytdlp || false
            })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                showToast(`Download started for "${video.title}"`, 'success');
                closePreview();
                pollTasks();
            }
        });
    }
});

// Open Folder
openFolderBtn.addEventListener('click', async () => {
    try {
        const resp = await fetch('/api/open-folder', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            showToast('Opening downloads folder in Explorer...', 'info');
        } else {
            showToast('Could not open folder.', 'error');
        }
    } catch (e) {
        showToast('Error requesting folder open.', 'error');
    }
});

// Clear Completed Tasks
clearCompletedBtn.addEventListener('click', async () => {
    try {
        await fetch('/api/clear-completed', { method: 'POST' });
        pollTasks();
        showToast('Cleared completed items.', 'info');
    } catch (e) {
        console.error(e);
    }
});

// Tasks Polling
async function pollTasks() {
    try {
        const resp = await fetch('/api/tasks');
        const data = await resp.json();
        if (data.success && data.tasks) {
            renderTasks(data.tasks);
        }
    } catch (e) {
        console.error("Task polling failed", e);
    }
}

function renderTasks(tasks) {
    if (tasks.length === 0) {
        emptyTasksNotice.classList.remove('hidden');
        tasksList.innerHTML = '';
        tasksList.appendChild(emptyTasksNotice);
        activeCountBadge.classList.add('hidden');
        return;
    }

    emptyTasksNotice.classList.add('hidden');
    tasksList.innerHTML = '';

    let activeCount = 0;

    tasks.forEach(task => {
        if (task.status === 'downloading' || task.status === 'queued') {
            activeCount++;
        }

        const taskEl = document.createElement('div');
        taskEl.className = 'bg-[#0f172a]/95 border border-slate-800 rounded-2xl p-3.5 sm:p-4 space-y-3 shadow-lg';
        
        let statusBadge = '';
        let progressClass = 'progress-active';

        if (task.status === 'completed') {
            statusBadge = '<span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i class="fa-solid fa-circle-check"></i> <span>Completed</span></span>';
            progressClass = 'bg-emerald-500';
        } else if (task.status === 'downloading') {
            statusBadge = '<span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"><i class="fa-solid fa-circle-notch fa-spin"></i> <span>Downloading</span></span>';
        } else if (task.status === 'queued') {
            statusBadge = '<span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20"><i class="fa-solid fa-clock"></i> <span>Queued</span></span>';
            progressClass = 'bg-amber-500';
        } else {
            statusBadge = `<span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20"><i class="fa-solid fa-circle-xmark"></i> <span>${escapeHtml(task.status)}</span></span>`;
            progressClass = 'bg-rose-500';
        }

        // Action buttons based on task status
        let actionsHtml = '';
        if (task.status === 'completed') {
            actionsHtml = `
                <button class="open-file-btn flex items-center space-x-1 text-xs font-semibold bg-emerald-600/15 hover:bg-emerald-600/25 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-xl transition active:scale-95" data-id="${task.id}" title="Play Video in Media Player">
                    <i class="fa-solid fa-play text-emerald-400 text-[11px]"></i>
                    <span>Play</span>
                </button>
            `;
        } else if (task.status === 'downloading' || task.status === 'queued') {
            actionsHtml = `
                <button class="cancel-task-btn text-xs text-rose-400 hover:text-white p-1.5 rounded-lg hover:bg-rose-950/80 transition" data-id="${task.id}" title="Cancel Download">
                    <i class="fa-solid fa-xmark text-sm"></i>
                </button>
            `;
        }

        taskEl.innerHTML = `
            <div class="flex items-center justify-between gap-3">
                <div class="flex items-center space-x-3 truncate">
                    <div class="w-9 h-9 rounded-xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center shrink-0 text-slate-300 text-sm">
                        <i class="fa-solid fa-video"></i>
                    </div>
                    <div class="truncate">
                        <div class="text-xs sm:text-sm font-bold text-white truncate" title="${escapeHtml(task.title)}">
                            ${escapeHtml(task.title)}
                        </div>
                        <div class="text-[11px] text-slate-400 font-mono truncate">
                            ${escapeHtml(task.filename)} • ${escapeHtml(task.quality)}
                        </div>
                    </div>
                </div>

                <div class="flex items-center space-x-2 shrink-0">
                    ${statusBadge}
                    ${actionsHtml}
                </div>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-slate-800/80 rounded-full h-2.5 overflow-hidden p-[1px] border border-slate-700/50">
                <div class="${progressClass} h-full transition-all duration-300 rounded-full" style="width: ${task.progress}%"></div>
            </div>

            <!-- Stats Row -->
            <div class="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>${escapeHtml(task.downloaded_bytes_formatted)} / ${escapeHtml(task.total_bytes_formatted)}</span>
                <div class="flex items-center space-x-3">
                    ${task.speed ? `<span><i class="fa-solid fa-gauge-high mr-1 text-slate-500"></i>${escapeHtml(task.speed)}</span>` : ''}
                    <span class="font-bold text-slate-200">${task.progress}%</span>
                </div>
            </div>

            ${task.error ? `
                <div class="text-xs text-rose-300 bg-rose-950/40 border border-rose-500/20 px-3 py-1.5 rounded-xl">
                    <i class="fa-solid fa-triangle-exclamation mr-1 text-rose-400"></i> ${escapeHtml(task.error)}
                </div>
            ` : ''}
        `;

        tasksList.appendChild(taskEl);
    });

    if (activeCount > 0) {
        activeCountBadge.textContent = activeCount;
        activeCountBadge.classList.remove('hidden');
    } else {
        activeCountBadge.classList.add('hidden');
    }
}

// Tasks List Click Delegations (Cancel & Open File)
tasksList.addEventListener('click', async (e) => {
    const cancelBtn = e.target.closest('.cancel-task-btn');
    if (cancelBtn) {
        const id = cancelBtn.dataset.id;
        try {
            await fetch(`/api/cancel/${id}`, { method: 'POST' });
            showToast('Download cancelled', 'info');
            pollTasks();
        } catch (e) {
            console.error(e);
        }
        return;
    }

    const openFileBtn = e.target.closest('.open-file-btn');
    if (openFileBtn) {
        const id = openFileBtn.dataset.id;
        try {
            const resp = await fetch('/api/open-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: id })
            });
            const data = await resp.json();
            if (data.success) {
                showToast('Playing video in Windows media player...', 'info');
            } else {
                showToast('Could not open video file directly.', 'error');
            }
        } catch (e) {
            showToast('Error requesting file launch.', 'error');
        }
        return;
    }
});

// Initialization
pollInterval = setInterval(pollTasks, 1000);
pollTasks();
