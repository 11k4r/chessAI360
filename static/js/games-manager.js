async function fetchGames() {
    const username = document.getElementById('username-input').value.trim();
    const btn = document.getElementById('fetch-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('btn-loader');
    const errorDiv = document.getElementById('error-msg');

    if (!username) return;

    // Reset State
    allGamesCache = [];
    currentGamesList = []; 
    availableArchives = [];
    archiveIndex = 0;
    currentOffset = 0;
    currentUserCache = username;
    isLoading = false;

    // UI Loading State
    btn.disabled = true;
    btn.classList.add('opacity-75');
    btnText.innerText = "Searching...";
    loader.classList.remove('hidden');
    errorDiv.classList.add('hidden');
    document.getElementById('games-container').innerHTML = ''; 

    try {
        if (currentPlatform === 'chesscom') {
            const archivesRes = await fetch(`https://api.chess.com/pub/player/${username}/games/archives`);
            if (!archivesRes.ok) throw new Error('User not found on Chess.com');
            
            const archivesData = await archivesRes.json();
            if (archivesData.archives.length === 0) throw new Error('No game history found.');

            availableArchives = archivesData.archives.reverse();
            await fetchNextMonth();
        } else if (currentPlatform === 'lichess') {
            const res = await fetch(`https://lichess.org/api/games/user/${username}?max=100&pgnInJson=true&clocks=true`, {
                headers: { 'Accept': 'application/x-ndjson' }
            });

            if (!res.ok) throw new Error('User not found on Lichess');

            const text = await res.text();
            const games = text.trim().split('\n').map(line => {
                if(!line) return null;
                try { return JSON.parse(line); } catch(e) { return null; }
            }).filter(g => g);

            if (games.length === 0) throw new Error('No game history found on Lichess.');

            allGamesCache = games.map(g => {
                let whiteRes = 'agreed';
                let blackRes = 'agreed'; 
                if (g.winner === 'white') { whiteRes = 'win'; blackRes = 'resigned'; }
                else if (g.winner === 'black') { blackRes = 'win'; whiteRes = 'resigned'; }
                
                return {
                    pgn: g.pgn, 
                    time_class: g.speed,
                    white: { 
                        username: g.players.white.user ? g.players.white.user.name : 'Anonymous', 
                        result: whiteRes, 
                        rating: g.players.white.rating || '?'
                    },
                    black: { 
                        username: g.players.black.user ? g.players.black.user.name : 'Anonymous', 
                        result: blackRes, 
                        rating: g.players.black.rating || '?'
                    },
                    end_time: Math.floor(g.createdAt / 1000)
                };
            });
        }

        if (allGamesCache.length === 0) throw new Error('No games found in recent history.');
        
        document.getElementById('import-view').classList.add('hidden');
        document.getElementById('games-list-view').classList.remove('hidden');
        document.getElementById('main-header').classList.add('hidden'); 
        
        renderNextBatch();

    } catch (err) {
        errorDiv.innerText = err.message;
        errorDiv.classList.remove('hidden');
    } finally {
        resetBtn();
    }
}

async function fetchNextMonth() {
    if (currentPlatform === 'lichess') return false; 
    if (archiveIndex >= availableArchives.length) return false;

    const url = availableArchives[archiveIndex];
    archiveIndex++; 

    const res = await fetch(url);
    const data = await res.json();
    const newGames = data.games.reverse();
    
    allGamesCache = allGamesCache.concat(newGames);
    return true; 
}

async function renderNextBatch() {
    if (isLoading) return;
    isLoading = true;

    const loader = document.getElementById('scroll-loader');
    const container = document.getElementById('games-container');
    
    loader.classList.remove('hidden');

    if (currentOffset + BATCH_SIZE >= allGamesCache.length) {
        await fetchNextMonth();
    }

    setTimeout(() => {
		const currentContainer = document.getElementById('games-container');
        if (!currentContainer) {
            isLoading = false;
            return;
        }
        if (currentOffset >= allGamesCache.length) {
            loader.classList.add('hidden');
            isLoading = false;
            return;
        }

        const batch = allGamesCache.slice(currentOffset, currentOffset + BATCH_SIZE);
        appendGamesToDOM(batch);
        currentOffset += BATCH_SIZE;
        
        loader.classList.add('hidden');
        isLoading = false;

        if (container.scrollHeight <= container.clientHeight && currentOffset < allGamesCache.length) {
            renderNextBatch();
        }
        
    }, 300);
}

function appendGamesToDOM(games) {
    const container = document.getElementById('games-container');
	if (!container) return;
    const startIndex = currentGamesList.length;
    currentGamesList = currentGamesList.concat(games);

    games.forEach((game, i) => {
        const globalIndex = startIndex + i;
        const timeClass = game.time_class; 
        const isWhite = game.white.username.toLowerCase() === currentUserCache.toLowerCase();
        const opponent = isWhite ? game.black : game.white;
        const myResult = isWhite ? game.white.result : game.black.result;
        
        let resultKey = 'loss';
        if (myResult === 'win') resultKey = 'win';
        else if (['agreed', 'repetition', 'stalemate', 'insufficient'].includes(myResult)) resultKey = 'draw';
        
        if (!activeFilters[timeClass]) return;
        if (!activeFilters[resultKey]) return;
        
        let resultColor = 'text-slate-500'; 
        let resultIcon = 'fa-minus';
        
        if (myResult === 'win') {
            resultColor = 'text-green-400';
            resultIcon = 'fa-trophy';
        } else if (['checkmated', 'resigned', 'timeout', 'abandoned'].includes(myResult)) {
            resultColor = 'text-red-400';
            resultIcon = 'fa-xmark';
        }

        const timeColor = TIME_STYLES[timeClass] || 'text-slate-500'; 

        const card = `
            <div onclick="handleClick(${globalIndex})" 
                 class="glass-panel p-4 rounded-xl flex items-center justify-between border-l-4 ${myResult === 'win' ? 'border-green-500' : (resultColor === 'text-red-400' ? 'border-red-500' : 'border-slate-500')} animate-fade-in cursor-pointer hover:bg-white/5 transition-colors">
                <div class="flex items-center gap-4">
                    <div class="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center ${resultColor} bg-opacity-20">
                        <i class="fa-solid ${resultIcon}"></i>
                    </div>
                    <div>
                        <div class="text-white font-bold text-sm">vs. ${opponent.username} <span class="text-xs text-slate-500">(${opponent.rating})</span></div>
                        <div class="text-xs font-bold uppercase tracking-wider ${timeColor}">
                            ${timeClass} <span class="text-slate-500 font-normal capitalize">• ${new Date(game.end_time * 1000).toLocaleDateString()}</span>
                        </div>
                    </div>
                </div>
                <div class="text-xs font-bold uppercase tracking-wider ${resultColor}">
                    ${myResult}
                </div>
            </div>
        `;
        container.innerHTML += card;
    });
}

function resetBtn() {
    const btn = document.getElementById('fetch-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('btn-loader');
    
    btn.disabled = false;
    btn.classList.remove('opacity-75');
    btnText.innerText = "Find Games";
    loader.classList.add('hidden');
}

function toggleFilter(key) {
    activeFilters[key] = !activeFilters[key];
    updateFilterUI(key);
    refreshGameList();
}

function updateFilterUI(key) {
    const btn = document.getElementById(`filter-${key}`);
    if (!btn) return; 
    
    if (activeFilters[key]) {
        btn.classList.add('active', 'bg-opacity-10');
        btn.classList.remove('opacity-25', 'grayscale');
    } else {
        btn.classList.remove('active', 'bg-opacity-10');
        btn.classList.add('opacity-25', 'grayscale');
    }
}

function resetFilters(enableAll) {
    Object.keys(activeFilters).forEach(k => activeFilters[k] = enableAll);
    Object.keys(activeFilters).forEach(k => updateFilterUI(k));
    refreshGameList();
}

function refreshGameList() {
    const container = document.getElementById('games-container');
    container.innerHTML = '';
    currentGamesList = []; 
    
    appendGamesToDOM(allGamesCache);
    currentOffset = allGamesCache.length;
    
    if (container.scrollHeight <= container.clientHeight) {
        renderNextBatch();
    }
}

function handleClick(index) {
    const game = currentGamesList[index];
    if (game) {
        selectGame(game);
    }
}

async function selectGame(game) {
    const pgn = game.pgn;
	
	if (!pgn) {
        alert("Sorry, no PGN data was found for this game.");
        return;
    }
	
    currentGameInfo = game;
    const isBlack = game.black.username.toLowerCase() === currentUserCache.toLowerCase();
    const userSide = isBlack ? 'black' : 'white';

    const tcBox = document.getElementById('time-control-box');
    tcBox.innerText = game.time_class;
    const timeColorClass = TIME_STYLES[game.time_class] || 'text-slate-400';
    tcBox.className = `flex items-center justify-center px-4 rounded-md bg-slate-800 border border-slate-700 font-bold text-xs uppercase tracking-wider ${timeColorClass}`;
    
    document.getElementById('games-list-view').classList.add('hidden');
    document.getElementById('import-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');

    initChessBoard(pgn); 
    board.orientation(userSide);
    updatePlayerInfo();  
    
    const loader = document.getElementById('analysis-loader');
    const content = document.getElementById('analysis-content');
    
    if(loader) {
        loader.classList.remove('hidden');
        loader.classList.remove('opacity-0'); 
    }
    
    if(content) {
        content.classList.remove('opacity-100');
        content.classList.add('opacity-0'); 
    }

    if (workerPool.length === 0) {
        const THREAD_COUNT = navigator.hardwareConcurrency || 4;
        for (let i = 0; i < THREAD_COUNT; i++) {
            const wDeep = createDeepWorker();
            wDeep.postMessage('uci');
            wDeep.postMessage('setoption name Threads value 1'); 
            wDeep.postMessage('setoption name Hash value 16');
            
            // Push the deep worker directly into the pool
            workerPool.push(wDeep);
        }
    }

    try {
        const analysisData = await processSingleGameInParallel(pgn);

        const payload = {
            pgn: pgn,
            analysis: analysisData,
			user_side: userSide
        };

        const response = await fetch('/api/analyze-game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const finalGameData = await response.json();

        currentAnalysisData = finalGameData; 
        
        if (currentAnalysisData && currentAnalysisData.position_metrics) {
            initEvalChart(currentAnalysisData.position_metrics);
            updateBoard(); 
        }

        if (loader) {
            loader.classList.add('opacity-0');
            setTimeout(() => loader.classList.add('hidden'), 500); 
        }
        if (content) {
            setTimeout(() => {
                content.classList.remove('opacity-0');
                content.classList.add('opacity-100');
            }, 300);
        }

    } catch (e) {
        console.error("Analysis Failed:", e);
        alert("Error: " + e.message);
        resetView();
    }
}

// Scroll Listener Initialization
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('games-container');
    if (container) {
        container.addEventListener('scroll', function() {
            const { scrollTop, scrollHeight, clientHeight } = this;
            if (scrollTop + clientHeight >= scrollHeight - 50) {
                renderNextBatch();
            }
        });
    }
});