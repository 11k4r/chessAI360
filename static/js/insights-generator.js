// ==========================================
// 1. Global State for Live Averages
// ==========================================
let runningStats = {
    totalGames: 0, wins: 0, losses: 0, draws: 0,
    metricsSum: { ACC: 0, TAC: 0, CAL: 0, STR: 0, INT: 0, ATK: 0, TMG: 0, DEF: 0, RES: 0, OPN: 0, MID: 0, END: 0 },
    batchesProcessed: 0,
    tcStats: { bullet: {w:0, l:0, d:0}, blitz: {w:0, l:0, d:0}, rapid: {w:0, l:0, d:0} },
    firstMoves: {}
};

// ==========================================
// 2. Main Execution Loop (Triggered by button)
// ==========================================
async function executeLiveInsights() {
    const BATCH_SIZE = 5; 
    const CHESSCOM_USER = "11k4r";
    const LICHESS_USER = "IdoIkar";
    
    fetchAndPaintProfile(CHESSCOM_USER);
    
    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    const progressBar = document.getElementById('progress-bar');
    
    if (progressContainer) progressContainer.classList.remove('hidden');
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.classList.remove('bg-green-500');
        progressBar.classList.add('bg-yellow-500');
    }
    
    runningStats = {
        totalGames: 0, wins: 0, losses: 0, draws: 0,
        metricsSum: { ACC: 0, TAC: 0, CAL: 0, STR: 0, INT: 0, ATK: 0, TMG: 0, DEF: 0, RES: 0, OPN: 0, MID: 0, END: 0 },
        batchesProcessed: 0,
        tcStats: { bullet: {w:0, l:0, d:0}, blitz: {w:0, l:0, d:0}, rapid: {w:0, l:0, d:0} },
        firstMoves: {},
        openings: {},
        endgames: {}  
    };

    if (progressText) progressText.innerText = "Fetching games from servers...";
    let allGamesToProcess = await fetchAllGames(CHESSCOM_USER, LICHESS_USER); 
    
    // 1. Separate all games (for fast stats) vs top 20 per TC (for deep stats)
    let allRawGames = [];
    let deepGamesQueue = [];

    for (const platform in allGamesToProcess) {
        for (const tc in allGamesToProcess[platform]) {
            const games = allGamesToProcess[platform][tc].games;
            allRawGames.push(...games);
            deepGamesQueue.push(...games.slice(0, 20)); // Limit deep analysis to 20 per TC
        }
    }
    
    if (allRawGames.length === 0) {
        if (progressText) progressText.innerText = "No recent games found.";
        return;
    }

    // 2. Send FAST batch (Stats, Results, Openings, Endgames) immediately
    if (progressText) progressText.innerText = "Extracting basic stats, repertoire, and endgames...";
    try {
        const res = await fetch('/api/analyze-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ games: allRawGames, analyzed_games: [] })
        });
        const fastMetrics = await res.json();
        // Update UI with all games counted
        updateLiveUI(fastMetrics, allRawGames.length, 0, deepGamesQueue.length);
    } catch (err) {
        console.error("Fast Batch Error:", err);
    }
    
    const totalQueueLength = deepGamesQueue.length;
    if (progressText) progressText.innerText = `Preparing engine for ${totalQueueLength} deep analyses...`;

    // 3. Process Deep Games in Batches
    if (workerPool.length === 0) {
        const THREAD_COUNT = navigator.hardwareConcurrency || 4;
        for (let i = 0; i < THREAD_COUNT; i++) {
            const wDeep = createDeepWorker();
            wDeep.postMessage('uci');
            wDeep.postMessage('setoption name Threads value 1'); 
            wDeep.postMessage('setoption name Hash value 16');
            workerPool.push(wDeep);
        }
    }

    let completedCount = 0;

    for (let i = 0; i < deepGamesQueue.length; i += BATCH_SIZE) {
        const batch = deepGamesQueue.slice(i, i + BATCH_SIZE);
        const analyzedBatch = [];

        // A. Run Client-Side Stockfish
        for (const game of batch) {
            try {
                const analysisData = await processSingleGameInParallel(game.pgn);
                analyzedBatch.push({ ...game, analysis: analysisData });
            } catch (err) {
                console.error("Game skip:", err);
            }
        }

        // B. Send Analyzed Batch to Server
        try {
            const res = await fetch('/api/analyze-batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ games: [], analyzed_games: analyzedBatch })
            });
            
            if (!res.ok) throw new Error("Server rejected the batch");
            const batchMetrics = await res.json();
            
            completedCount += batch.length;
            // gamesInBatch is 0 here so we don't double-count total games on the UI
            updateLiveUI(batchMetrics, 0, completedCount, totalQueueLength);
        } catch (err) {
            console.error("Batch send failed:", err);
            completedCount += batch.length; 
            updateLiveUI(null, 0, completedCount, totalQueueLength);
        }
    }
    
    if (progressText) progressText.innerText = "Analysis Complete!";
    if (progressBar) {
        progressBar.classList.add('bg-green-500');
        progressBar.classList.remove('bg-yellow-500');
    }
}

// ==========================================
// 3. UI Updater
// ==========================================
function updateLiveUI(batchMetrics, gamesInBatch, completedCount, totalCount) {
    // 1. Update Progress Bar
    const percent = Math.round((completedCount / totalCount) * 100);
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.innerText = `${completedCount} / ${totalCount} Games Analyzed`;

    // Guard against failed server batches
    if (!batchMetrics || !batchMetrics.performance) return; 

    // Aggregate Global Stats
    runningStats.totalGames += gamesInBatch;
    runningStats.wins += batchMetrics.performance.wins || 0;
    
    // Aggregate Time Control Stats
    const batchTC = batchMetrics.performance.tc_stats || {};
    ['bullet', 'blitz', 'rapid'].forEach(tc => {
        if (batchTC[tc]) {
            runningStats.tcStats[tc].w += batchTC[tc].w;
            runningStats.tcStats[tc].l += batchTC[tc].l;
            runningStats.tcStats[tc].d += batchTC[tc].d;
        }
    });

    // Aggregate First Moves
    const batchMoves = batchMetrics.performance.first_moves || {};
    for (const [move, count] of Object.entries(batchMoves)) {
        runningStats.firstMoves[move] = (runningStats.firstMoves[move] || 0) + count;
    }

    // Determine the Most Played First Move
    let topMove = '-';
    let maxCount = 0;
    for (const [move, count] of Object.entries(runningStats.firstMoves)) {
        if (count > maxCount) {
            maxCount = count;
            topMove = move;
        }
    }

    // ---> THE MISSING BLOCK: Aggregate the Metrics and Increment Batches <---
    runningStats.batchesProcessed += 1;
    if (batchMetrics.metrics) {
        for (const key in runningStats.metricsSum) {
            runningStats.metricsSum[key] += batchMetrics.metrics[key] || 0;
        }
    }
    // -------------------------------------------------------------------------

    const avgWinRate = runningStats.totalGames > 0 ? Math.round((runningStats.wins / runningStats.totalGames) * 100) : 0;
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    
    // Paint the UI
    setText('stat-win-rate', `${avgWinRate}%`);
    setText('stat-first-move', `1. ${topMove}`);

    // Paint Time Control Stats
    ['bullet', 'blitz', 'rapid'].forEach(tc => {
        setText(`stat-${tc}-w`, runningStats.tcStats[tc].w);
        setText(`stat-${tc}-l`, runningStats.tcStats[tc].l);
        setText(`stat-${tc}-d`, runningStats.tcStats[tc].d);
    });
    
    // 5. Update the Metrics Bars
    let activeMetricsCount = 0;
    let ovrSum = 0;

    for (const key in runningStats.metricsSum) {
        // Now this math will work perfectly
        const avgVal = Math.round(runningStats.metricsSum[key] / runningStats.batchesProcessed);
        
        // Find the corresponding bar in the DOM and update it
        const metricRows = document.querySelectorAll('.metric-row');
        metricRows.forEach(row => {
            const nameEl = row.querySelector('.metric-name');
            if (nameEl && nameEl.innerText === key) {
                const valEl = row.querySelector('.metric-value');
                const fillEl = row.querySelector('.metric-bar-fill');
                
                if (valEl) valEl.innerText = avgVal;
                if (fillEl) fillEl.style.width = `${avgVal}%`;
            }
        });

        // Core stats for OVR calculation
        if (['ACC', 'TAC', 'STR', 'CAL'].includes(key)) {
            ovrSum += avgVal;
            activeMetricsCount++;
        }
    }

    // 6. Update OVR Hexagon
    if (activeMetricsCount > 0) {
        setText('overall-score', Math.round(ovrSum / activeMetricsCount));
    }
	
	const batchOps = batchMetrics.repertoire?.openings || {};
    for (const [opName, stats] of Object.entries(batchOps)) {
        if (!runningStats.openings[opName]) runningStats.openings[opName] = {w:0, l:0, d:0, color: stats.color};
        runningStats.openings[opName].w += stats.w;
        runningStats.openings[opName].l += stats.l;
        runningStats.openings[opName].d += stats.d;
    }

    // 2. Accumulate Endgames
    const batchEgs = batchMetrics.repertoire?.endgames || {};
    for (const [egName, stats] of Object.entries(batchEgs)) {
        if (!runningStats.endgames[egName]) runningStats.endgames[egName] = {w:0, l:0, d:0};
        runningStats.endgames[egName].w += stats.w;
        runningStats.endgames[egName].l += stats.l;
        runningStats.endgames[egName].d += stats.d;
    }

    // 3. Render Openings List
    const opArray = Object.entries(runningStats.openings).map(([name, s]) => ({name, ...s, total: s.w+s.l+s.d}));
    opArray.sort((a,b) => b.total - a.total); // Sort by most played
    
    const opHTML = opArray.map(op => {
        const wr = Math.round((op.w / op.total) * 100);
        const colorClass = op.color === 'white' ? 'bg-slate-200' : 'bg-slate-800 border border-slate-600';
        const winColor = wr >= 50 ? 'text-green-400' : 'text-red-400';
        
        return `<div class="bg-black/20 rounded-lg p-2.5 border border-white/5 flex items-center justify-between hover:bg-white/5 transition-colors">
            <div class="flex items-center gap-3 overflow-hidden">
                <div class="w-2.5 h-2.5 flex-none rounded-full ${colorClass}" title="Played as ${op.color}"></div>
                <div class="text-[11px] font-bold text-slate-200 truncate" title="${op.name}">${op.name}</div>
            </div>
            <div class="flex items-center gap-6 flex-none pl-2">
                <div class="text-[10px] font-mono text-slate-500 w-6 text-right">${op.total}</div>
                <div class="text-[11px] font-bold font-mono ${winColor} w-8 text-right">${wr}%</div>
            </div>
        </div>`;
    }).join('');
    
    document.getElementById('openings-list').innerHTML = opHTML || '<div class="text-xs text-slate-500 text-center mt-4">No data yet...</div>';

    // 4. Render Endgames List
    const egArray = Object.entries(runningStats.endgames).map(([name, s]) => ({name, ...s, total: s.w+s.l+s.d}));
    egArray.sort((a,b) => b.total - a.total); // Sort by most played
    
    const egHTML = egArray.map(eg => {
        const wr = Math.round((eg.w / eg.total) * 100);
        const winColor = wr >= 50 ? 'text-green-400' : 'text-red-400';
        
        return `<div class="bg-black/20 rounded-lg p-2.5 border border-white/5 flex items-center justify-between hover:bg-white/5 transition-colors">
            <div class="flex items-center gap-3 overflow-hidden">
                <i class="fa-solid fa-chess flex-none text-slate-600 text-[10px]"></i>
                <div class="text-[11px] font-bold text-slate-200 truncate" title="${eg.name}">${eg.name}</div>
            </div>
            <div class="flex items-center gap-6 flex-none pl-2">
                <div class="text-[10px] font-mono text-slate-500 w-6 text-right">${eg.total}</div>
                <div class="text-[11px] font-bold font-mono ${winColor} w-8 text-right">${wr}%</div>
            </div>
        </div>`;
    }).join('');
    
    document.getElementById('endgames-list').innerHTML = egHTML || '<div class="text-xs text-slate-500 text-center mt-4">No endgames reached yet...</div>';
}

// ==========================================
// 4. Data Fetching & Limiting
// ==========================================
async function fetchAllGames(chesscomUser, lichessUser) {
    const cutoffMs = Date.now() - (360 * 24 * 60 * 60 * 1000);
    const cutoffSec = Math.floor(cutoffMs / 1000);
    const payload = { chesscom: {}, lichess: {} };

    // --- Chess.com ---
    try {
        const archivesRes = await fetch(`https://api.chess.com/pub/player/${chesscomUser}/games/archives`);
        if (archivesRes.ok) {
            const archivesData = await archivesRes.json();
            let allChesscomGames = [];
            
            for (const archiveUrl of archivesData.archives.reverse()) {
                const parts = archiveUrl.split('/');
                const year = parseInt(parts[parts.length - 2]);
                const month = parseInt(parts[parts.length - 1]);
                const archiveDate = new Date(year, month - 1, 1).getTime();
                
                // Stop fetching if older than 360+31 days
                if (archiveDate < cutoffMs - (31 * 24 * 60 * 60 * 1000)) break;

                const res = await fetch(archiveUrl);
                const monthData = await res.json();
                const validGames = monthData.games.filter(g => g.end_time >= cutoffSec);
                allChesscomGames = allChesscomGames.concat(validGames);
            }
            payload.chesscom = groupAndFormatGames(allChesscomGames, chesscomUser, 'chesscom');
        }
    } catch (e) {
        console.error("Error fetching Chess.com:", e);
    }

    // --- Lichess ---
    try {
        const res = await fetch(`https://lichess.org/api/games/user/${lichessUser}?since=${cutoffMs}&pgnInJson=true&clocks=true`, {
            headers: { 'Accept': 'application/x-ndjson' }
        });
        
        if (res.ok) {
            const text = await res.text();
            const lichessGames = text.trim().split('\n').map(line => {
                if(!line) return null;
                try { return JSON.parse(line); } catch(e) { return null; }
            }).filter(g => g);
            payload.lichess = groupAndFormatGames(lichessGames, lichessUser, 'lichess');
        }
    } catch (e) {
        console.error("Error fetching Lichess:", e);
    }

    return payload;
}

// ==========================================
// 5. Data Normalization Helper
// ==========================================
function groupAndFormatGames(rawGames, username, platform) {
    const grouped = {};

    rawGames.forEach(g => {
        const pgn = g.pgn || '';
        if (!pgn) return;

        // Extract exact Time Control
        const tcMatch = pgn.match(/\[TimeControl\s+"([^"]+)"\]/);
        const timeControl = tcMatch ? tcMatch[1] : 'unknown';

        // Determine User Side, Result, & Timestamp
        let userSide = 'white';
        let result = 'draw';
        let timestamp = 0;

        if (platform === 'chesscom') {
            userSide = g.white.username.toLowerCase() === username.toLowerCase() ? 'white' : 'black';
            const myResultCode = userSide === 'white' ? g.white.result : g.black.result;
            
            if (myResultCode === 'win') result = 'win';
            else if (['checkmated', 'resigned', 'timeout', 'abandoned', 'lose'].includes(myResultCode)) result = 'loss';
            
            timestamp = g.end_time * 1000;
        } 
        else if (platform === 'lichess') {
            const whitePlayer = g.players.white.user ? g.players.white.user.name : '';
            userSide = whitePlayer.toLowerCase() === username.toLowerCase() ? 'white' : 'black';
            
            if (g.winner) result = g.winner === userSide ? 'win' : 'loss';
            
            timestamp = g.createdAt;
        }

        if (!grouped[timeControl]) {
            grouped[timeControl] = { total_games: 0, games: [] };
        }

        grouped[timeControl].games.push({
            pgn: pgn,
            result: result,
            user_side: userSide,
            timestamp: timestamp
        });
    });

    // Enforce the 100-game limit per time control
    for (const tc in grouped) {
        grouped[tc].games.sort((a, b) => b.timestamp - a.timestamp);
        grouped[tc].games = grouped[tc].games.slice(0, 100);
        grouped[tc].total_games = grouped[tc].games.length; 
    }

    return grouped;
}

// ==========================================
// Profile & Ratings Fetcher
// ==========================================
async function fetchAndPaintProfile(username) {
    try {
        // 1. Fetch Basic Profile (Avatar, Title, Username)
        const profileRes = await fetch(`https://api.chess.com/pub/player/${username}`);
        if (profileRes.ok) {
            const profile = await profileRes.json();
            
            document.getElementById('player-username').innerText = profile.username || username;
            
            if (profile.avatar) {
                document.getElementById('player-img').src = profile.avatar;
            }
            if (profile.title) {
                const badge = document.getElementById('title-badge');
                if (badge) {
                    badge.innerText = profile.title;
                    badge.classList.remove('hidden');
                }
            }
			
			if (profile.country) {
                // Extracts "us" from "https://api.chess.com/pub/country/us"
                const countryCode = profile.country.split('/').pop().toLowerCase();
                const flagImg = document.getElementById('country-flag');
                if (flagImg && countryCode) {
                    flagImg.src = `https://flagcdn.com/w40/${countryCode}.png`;
                }
            }
        }

        // 2. Fetch Current Ratings
        const statsRes = await fetch(`https://api.chess.com/pub/player/${username}/stats`);
        if (statsRes.ok) {
            const stats = await statsRes.json();
            
            const rapidRating = stats.chess_rapid?.last?.rating || '?';
            const blitzRating = stats.chess_blitz?.last?.rating || '?';
            const bulletRating = stats.chess_bullet?.last?.rating || '?';

            document.getElementById('rating-rapid').innerText = rapidRating;
            document.getElementById('rating-blitz').innerText = blitzRating;
            document.getElementById('rating-bullet').innerText = bulletRating;
        }
    } catch (e) {
        console.error("Failed to fetch profile info:", e);
    }
}