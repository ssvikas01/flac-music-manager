/* ========================================================
   FLAC Library Manager — App Logic
   ======================================================== */

let data = [];
let sortCol = 'artist';
let sortDesc = false;
let activeFilter = 'all';

document.addEventListener('DOMContentLoaded', init);

function init() {
    fetchStats();
    fetchSongs();

    // Search
    const searchEl = document.getElementById('search');
    let debounce;
    searchEl.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(render, 120);
    });

    // Sort dropdown
    document.getElementById('sort-by').addEventListener('change', e => {
        sortCol = e.target.value;
        render();
    });

    // Sort direction toggle
    document.getElementById('sort-dir').addEventListener('click', e => {
        sortDesc = !sortDesc;
        e.currentTarget.classList.toggle('flipped', sortDesc);
        render();
    });

    // Quality filter chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.dataset.filter;
            render();
        });
    });
}

// ===== Fetch Stats =====
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const s = await res.json();

        // Top bar
        document.getElementById('topbar-stats').innerHTML = `
            <div><strong>${s.total_songs.toLocaleString()}</strong> tracks</div>
            <div><strong>${s.total_albums.toLocaleString()}</strong> albums</div>
            <div><strong>${s.total_artists.toLocaleString()}</strong> artists</div>
        `;

        // Stat cards
        const qb = s.quality_breakdown || [];
        const hi = qb.find(q => q.bit_depth === 24);
        const cd = qb.find(q => q.bit_depth === 16 && q.sample_rate === 44100);

        document.getElementById('stats-row').innerHTML = `
            <div class="stat-card">
                <div class="label">Total Tracks</div>
                <div class="value">${s.total_songs.toLocaleString()}</div>
            </div>
            <div class="stat-card">
                <div class="label">Library Size</div>
                <div class="value">${s.total_gb}<small>GB</small></div>
            </div>
            <div class="stat-card">
                <div class="label">Total Duration</div>
                <div class="value">${s.total_hours}<small>hrs</small></div>
            </div>
            <div class="stat-card">
                <div class="label">24-bit Tracks</div>
                <div class="value">${hi ? (hi.cnt || hi.count || 0).toLocaleString() : '0'}</div>
            </div>
            <div class="stat-card">
                <div class="label">CD Quality</div>
                <div class="value">${cd ? (cd.cnt || cd.count || 0).toLocaleString() : '0'}</div>
            </div>
        `;
    } catch (e) {
        console.error('Stats fetch failed', e);
    }
}

// ===== Fetch Songs =====
async function fetchSongs() {
    try {
        const res = await fetch('/api/songs');
        const text = await res.text();
        data = JSON.parse(text);
        if (data.error) throw new Error(data.error);
        render();
    } catch (e) {
        document.getElementById('song-list').innerHTML =
            `<div class="loading-state" style="color:var(--red)">
                <p>Failed to load library</p>
                <p style="font-size:0.8rem;opacity:0.7">${e.message}</p>
            </div>`;
    }
}

// ===== Helpers =====
function fmt(sec) {
    if (!sec) return '—';
    const total = Math.round(sec);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const ss = s.toString().padStart(2, '0');
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${ss}`;
    return `${m}:${ss}`;
}

function fmtSize(bytes) {
    if (!bytes) return '—';
    const mb = bytes / (1024 * 1024);
    return mb >= 1000 ? (mb / 1024).toFixed(2) + ' GB' : mb.toFixed(1) + ' MB';
}

function fmtRate(hz) {
    if (!hz) return '—';
    return (hz / 1000).toFixed(1) + ' kHz';
}

// ===== Render =====
function render() {
    const query = document.getElementById('search').value.toLowerCase();
    const list = document.getElementById('song-list');

    // Filter
    let filtered = data.filter(s => {
        // Text search
        const match = !query || Object.values(s).some(v => String(v).toLowerCase().includes(query));

        // Quality filter
        let qMatch = true;
        if (activeFilter === '24bit') qMatch = s.bit_depth === 24;
        else if (activeFilter === 'hires') qMatch = s.sample_rate > 48000;
        else if (activeFilter === 'cd') qMatch = s.bit_depth === 16 && s.sample_rate === 44100;

        return match && qMatch;
    });

    // Sort
    filtered.sort((a, b) => {
        let va = a[sortCol], vb = b[sortCol];
        if (va == null) va = '';
        if (vb == null) vb = '';
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return sortDesc ? 1 : -1;
        if (va > vb) return sortDesc ? -1 : 1;
        return 0;
    });

    // Result count
    document.getElementById('result-count').textContent = `${filtered.length.toLocaleString()} tracks`;

    // Empty state
    if (!filtered.length) {
        list.innerHTML = `<div class="loading-state"><p>No tracks match your filters.</p></div>`;
        return;
    }

    // Build rows — highlight the active sort field in every row
    const html = filtered.map(s => {
        const isHiRes = s.bit_depth === 24 || s.sample_rate > 48000;
        const badgeClass = isHiRes ? 'spec-badge hires' : 'spec-badge standard';
        const badgeLabel = isHiRes ? 'Hi-Res' : 'CD';

        // Helper: wrap a value in a highlight span when it's the sort key
        const hl = (key, display) =>
            sortCol === key
                ? `<span class="sort-highlight">${display}</span>`
                : display;

        // ── Track Info ───────────────────────────────────────────────────
        const titleEl   = hl('title',        esc(s.title));
        const artistEl  = hl('artist',       esc(s.artist));
        const albumEl   = hl('album',        esc(s.album));
        const yearEl    = hl('release_year', s.release_year ? s.release_year : '—');
        const trackEl   = s.track_number ? hl('track_number', '#' + s.track_number) : '';

        // ── Audio Specs ──────────────────────────────────────────────────
        const bitEl     = hl('bit_depth',   s.bit_depth + '-bit');
        const srEl      = hl('sample_rate', fmtRate(s.sample_rate));
        const brEl      = hl('bitrate',     s.bitrate ? s.bitrate : '—');
        const szEl      = hl('file_size',   fmtSize(s.file_size));
        const fmtEl     = hl('file_format', s.file_format || '—');

        // ── Classification ───────────────────────────────────────────────
        const genreEl   = hl('genre',       esc(s.genre) || '—');
        const listEl    = s.playlists ? hl('playlists', '♫ ' + esc(s.playlists)) : '';

        // ── Engagement ───────────────────────────────────────────────────
        const durEl     = hl('duration',    fmt(s.duration));
        const playsEl   = hl('play_count',  s.play_count ? s.play_count + ' plays' : '—');
        const ratingEl  = s.rating ? hl('rating', '★ ' + s.rating.toFixed(1)) : '';

        return `<div class="song-row" onclick="playTrack(${s.song_id}, this)" title="Click to play in Astra">
            <button class="play-action-btn" aria-label="Play song" onclick="event.stopPropagation(); playTrack(${s.song_id}, this.closest('.song-row'))">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
            </button>
            <div class="track-info">
                <div class="track-title">${titleEl}</div>
                <div class="track-sub">
                    <span class="artist-name">${artistEl}</span>
                    <span class="sep">·</span>
                    <span>${albumEl}</span>
                    <span class="sep">·</span>
                    <span class="year-chip">${yearEl}</span>
                    ${trackEl ? `<span class="sep">·</span><span>${trackEl}</span>` : ''}
                </div>
            </div>
            <div class="audio-specs">
                <span class="${badgeClass}">${badgeLabel} · ${fmtEl} ${bitEl}</span>
                <span class="spec-detail">${srEl} · ${brEl} · ${szEl}</span>
            </div>
            <div class="classification">
                <div class="genre-name">${genreEl}</div>
                ${listEl ? `<div class="playlist-name">${listEl}</div>` : ''}
            </div>
            <div class="engagement">
                <div class="dur">${durEl}</div>
                <div class="plays" id="plays-${s.song_id}">${playsEl}${ratingEl ? ' · <span class="rating-star">' + ratingEl + '</span>' : ''}</div>
            </div>
        </div>`;
    });

    list.innerHTML = html.join('');
}

let currentSongId = null;
let currentSongIndex = -1;
let audioElement = null;

document.addEventListener('DOMContentLoaded', () => {
    init();
    setupAudioPlayer();
});

function setupAudioPlayer() {
    audioElement = document.getElementById('audio-engine');
    const playBtn = document.getElementById('btn-play-pause');
    const iconPlay = document.getElementById('icon-play');
    const iconPause = document.getElementById('icon-pause');
    const progressBar = document.getElementById('progress-bar');
    const currTimeEl = document.getElementById('curr-time');
    const totalTimeEl = document.getElementById('total-time');

    if (!audioElement) return;

    audioElement.addEventListener('play', () => {
        iconPlay.style.display = 'none';
        iconPause.style.display = 'block';
    });

    audioElement.addEventListener('pause', () => {
        iconPlay.style.display = 'block';
        iconPause.style.display = 'none';
    });

    audioElement.addEventListener('timeupdate', () => {
        if (!audioElement.duration) return;
        const pct = (audioElement.currentTime / audioElement.duration) * 100;
        progressBar.value = pct;
        currTimeEl.textContent = fmt(audioElement.currentTime);
        totalTimeEl.textContent = fmt(audioElement.duration);
    });

    audioElement.addEventListener('ended', () => {
        playNextTrack();
    });

    // Spacebar to pause/play
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
            e.preventDefault();
            togglePlayPause();
        }
    });
}

async function playTrack(songId, rowEl) {
    try {
        const item = data.find(s => s.song_id === songId);
        if (!item) return;

        currentSongId = songId;
        currentSongIndex = data.findIndex(s => s.song_id === songId);

        // Highlight row
        document.querySelectorAll('.song-row').forEach(r => r.classList.remove('playing'));
        if (rowEl) {
            rowEl.classList.add('playing');
        }

        // Update player bar info
        document.getElementById('player-title').textContent = item.title;
        document.getElementById('player-sub').textContent = `${item.artist} · ${item.album} (${item.bit_depth}-bit / ${fmtRate(item.sample_rate)})`;

        // Load & stream directly in browser
        if (!audioElement) audioElement = document.getElementById('audio-engine');
        audioElement.src = `/stream/${songId}`;
        audioElement.play().catch(e => console.log('Autoplay policy or audio decode notice:', e));

        // Call backend API to record play count in database
        fetch(`/api/play/${songId}`, { method: 'POST' }).then(r => r.json()).then(resData => {
            if (resData.success) {
                item.play_count = resData.play_count;
                const playsCell = document.getElementById(`plays-${songId}`);
                if (playsCell) playsCell.textContent = `${item.play_count} plays`;
            }
        });

    } catch (err) {
        console.error('Failed to trigger play:', err);
    }
}

function togglePlayPause() {
    if (!audioElement || !audioElement.src) {
        if (data.length > 0) playTrack(data[0].song_id);
        return;
    }
    if (audioElement.paused) {
        audioElement.play();
    } else {
        audioElement.pause();
    }
}

function playNextTrack() {
    if (currentSongIndex < data.length - 1) {
        playTrack(data[currentSongIndex + 1].song_id);
    }
}

function playPrevTrack() {
    if (currentSongIndex > 0) {
        playTrack(data[currentSongIndex - 1].song_id);
    }
}

function seekTrack(pct) {
    if (audioElement && audioElement.duration) {
        audioElement.currentTime = (pct / 100) * audioElement.duration;
    }
}

function setVolume(val) {
    if (audioElement) {
        audioElement.volume = val / 100;
    }
}

async function launchInAstra() {
    if (!currentSongId) {
        alert('Please select a song first to open in Astra.');
        return;
    }
    try {
        const res = await fetch(`/api/play/${currentSongId}?astra=true`, { method: 'POST' });
        const json = await res.json();
        if (json.success) {
            alert(`Opening in Astra: ${json.message}`);
        }
    } catch (e) {
        console.error('Astra launch error:', e);
    }
}


function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}
