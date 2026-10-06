// Application State
let detectedVideos = [];
let pollInterval = null;
let currentPreviewItem = null;

// DOM Elements
const scanForm = document.getElementById('scanForm');
const urlInput = document.getElementById('urlInput');
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
    toast.className = `toast pointer-events-auto flex items-center space-x-2 px-4 py-3 rounded-xl shadow-xl text-xs sm:text-sm font-medium border backdrop-blur-md ${
        type === 'success' 
            ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/30' 
            : type === 'error'
            ? 'bg-rose-950/90 text-rose-200 border-rose-500/30'
            : 'bg-slate-900/90 text-slate-200 border-slate-700/60'
    }`;
    
    const icon = type === 'success' ? 'fa-circle-check text-emerald-400' 
               : type === 'error' ? 'fa-triangle-exclamation text-rose-400' 
               : 'fa-circle-info text-indigo-400';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Clipboard Paste
pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            urlInput.value = text;
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
        scanForm.dispatchEvent(new Event('submit'));
    });
});

// Scan Form Submission
scanForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    scanBtn.disabled = true;
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
            showToast('No downloadable videos could be located on this page.', 'error');
        } else {
            showToast(data.error || 'Failed to scan page.', 'error');
        }
    } catch (err) {
        showToast('Connection error while contacting server.', 'error');
    } finally {
        scanBtn.disabled = false;
        scanLoading.classList.add('hidden');
    }
});

// Render Video Cards
function renderVideoCards(videos, currentUrl) {
    resultsCount.textContent = videos.length;
    resultsUrl.textContent = currentUrl;
    videoCardsGrid.innerHTML = '';
    selectAllCheckbox.checked = false;
    updateSelectedCount();

    videos.forEach((video, index) => {
        const card = document.createElement('div');
        card.className = 'video-card group relative bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden flex flex-col justify-between shadow-lg';
        card.dataset.index = index;

        const defaultPoster = video.poster || '';
        const posterImgHtml = defaultPoster 
            ? `<img src="${escapeHtml(defaultPoster)}" alt="${escapeHtml(video.title)}" class="w-full h-full object-cover transition duration-300 group-hover:scale-105" onerror="this.parentElement.innerHTML='<div class=\'w-full h-full flex items-center justify-center bg-slate-800\'><i class=\'fa-solid fa-film text-3xl text-slate-600\'></i></div>'">`
            : `<div class="w-full h-full flex items-center justify-center bg-slate-800/80"><i class="fa-solid fa-film text-3xl text-slate-600"></i></div>`;

        let formatOptions = '';
        if (video.formats && video.formats.length > 0) {
            video.formats.forEach((fmt) => {
                formatOptions += `<option value="${escapeHtml(fmt.url)}">${escapeHtml(fmt.quality || 'Video')}</option>`;
            });
        } else {
            formatOptions = `<option value="${escapeHtml(video.default_url)}">Original Stream</option>`;
        }

        card.innerHTML = `
            <div>
                <!-- Thumbnail & Media Details -->
                <div class="relative aspect-video bg-black/60 overflow-hidden">
                    ${posterImgHtml}
                    
                    <div class="absolute top-2.5 left-2.5 z-10">
                        <input type="checkbox" class="video-checkbox w-4 h-4 rounded border-slate-600 bg-slate-900/80 text-indigo-600 focus:ring-indigo-500 cursor-pointer" data-index="${index}">
                    </div>

                    ${video.duration_formatted ? `
                        <div class="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/70 backdrop-blur-xs text-[11px] font-mono font-medium text-white">
                            ${escapeHtml(video.duration_formatted)}
                        </div>
                    ` : ''}

                    <div class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-900/80 backdrop-blur-md text-slate-300 border border-slate-700/50">
                        ${escapeHtml(video.source_type)}
                    </div>

                    <button class="preview-btn absolute inset-0 m-auto w-12 h-12 rounded-full bg-indigo-600/90 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200 transform scale-90 group-hover:scale-100 hover:bg-indigo-500 shadow-xl" data-index="${index}">
                        <i class="fa-solid fa-play ml-1"></i>
                    </button>
                </div>

                <div class="p-4 space-y-3">
                    <h4 class="text-sm font-semibold text-white line-clamp-2 leading-snug" title="${escapeHtml(video.title)}">
                        ${escapeHtml(video.title)}
                    </h4>

                    <div class="flex items-center space-x-2 text-xs">
                        <label class="text-slate-400 font-medium shrink-0">Quality:</label>
                        <select class="quality-select w-full bg-slate-950/80 border border-slate-700/80 text-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500" data-index="${index}">
                            ${formatOptions}
                        </select>
                    </div>
                </div>
            </div>

            <div class="p-4 pt-0 grid grid-cols-2 gap-2">
                <button class="preview-btn-bottom flex items-center justify-center space-x-1.5 text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/60 py-2 rounded-xl transition" data-index="${index}">
                    <i class="fa-solid fa-eye"></i>
                    <span>Preview</span>
                </button>
                <button class="download-card-btn flex items-center justify-center space-x-1.5 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white py-2 rounded-xl transition shadow-md shadow-indigo-600/20" data-index="${index}">
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

// Checkboxes
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

// Click Handling
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

// Single Download
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
            showToast(`Started downloading "${video.title}"`, 'success');
            pollTasks();
        } else {
            showToast(data.error || 'Download failed to start.', 'error');
        }
    } catch (e) {
        showToast('Error queuing download.', 'error');
    }
}

// Batch Selected
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
        showToast('Batch download failed.', 'error');
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

// Preview
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
            showToast('Opening downloads folder in Windows Explorer...', 'info');
        } else {
            showToast('Could not open folder automatically.', 'error');
        }
    } catch (e) {
        showToast('Error requesting folder opening.', 'error');
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
        taskEl.className = 'bg-slate-900/90 border border-slate-800 rounded-xl p-3 sm:p-4 space-y-2.5 shadow-sm';
        
        let statusBadge = '';
        let progressColor = 'bg-indigo-600';

        if (task.status === 'completed') {
            statusBadge = '<span class="inline-flex items-center space-x-1 text-emerald-400 font-semibold text-xs"><i class="fa-solid fa-circle-check"></i> <span>Completed</span></span>';
            progressColor = 'bg-emerald-500';
        } else if (task.status === 'downloading') {
            statusBadge = '<span class="inline-flex items-center space-x-1 text-indigo-400 font-semibold text-xs"><i class="fa-solid fa-circle-notch fa-spin"></i> <span>Downloading</span></span>';
            progressColor = 'bg-indigo-500';
        } else if (task.status === 'queued') {
            statusBadge = '<span class="inline-flex items-center space-x-1 text-amber-400 font-semibold text-xs"><i class="fa-solid fa-clock"></i> <span>Queued</span></span>';
            progressColor = 'bg-amber-500';
        } else {
            statusBadge = `<span class="inline-flex items-center space-x-1 text-rose-400 font-semibold text-xs"><i class="fa-solid fa-circle-xmark"></i> <span>${escapeHtml(task.status)}</span></span>`;
            progressColor = 'bg-rose-500';
        }

        taskEl.innerHTML = `
            <div class="flex items-center justify-between gap-3">
                <div class="flex items-center space-x-3 truncate">
                    <div class="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center shrink-0 text-slate-400 text-xs">
                        <i class="fa-solid fa-video"></i>
                    </div>
                    <div class="truncate">
                        <div class="text-xs sm:text-sm font-semibold text-white truncate" title="${escapeHtml(task.title)}">
                            ${escapeHtml(task.title)}
                        </div>
                        <div class="text-[11px] text-slate-400 font-mono truncate">
                            ${escapeHtml(task.filename)} • ${escapeHtml(task.quality)}
                        </div>
                    </div>
                </div>

                <div class="flex items-center space-x-3 shrink-0">
                    ${statusBadge}
                    ${task.status === 'downloading' || task.status === 'queued' ? `
                        <button class="cancel-task-btn text-xs text-rose-400 hover:text-rose-300 p-1.5 rounded hover:bg-slate-800 transition" data-id="${task.id}" title="Cancel">
                            <i class="fa-solid fa-xmark"></i>
                        </button>
                    ` : ''}
                </div>
            </div>

            <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div class="${progressColor} h-full transition-all duration-300 rounded-full" style="width: ${task.progress}%"></div>
            </div>

            <div class="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>${escapeHtml(task.downloaded_bytes_formatted)} / ${escapeHtml(task.total_bytes_formatted)}</span>
                <div class="flex items-center space-x-3">
                    ${task.speed ? `<span><i class="fa-solid fa-gauge-high mr-1"></i>${escapeHtml(task.speed)}</span>` : ''}
                    <span class="font-bold text-slate-300">${task.progress}%</span>
                </div>
            </div>
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

// Cancel
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
    }
});

clearCompletedBtn.addEventListener('click', pollTasks);
pollInterval = setInterval(pollTasks, 1000);
pollTasks();
