// ADD forceRefresh = false
async function fetchGames(directUsername = null, forceRefresh = false) {
    const inputField = document.getElementById('username-input');
    const username = directUsername || (inputField ? inputField.value.trim() : '');

    if (!username) return;

    // Safety Sync: Instantly memorize the username for the active tab
    if (currentPlatform === 'chesscom') {
        window.typedChesscom = username;
    } else if (currentPlatform === 'lichess') {
        window.typedLichess = username;
    }

    if (inputField) {
        inputField.value = username;
    }

    let isMyProfile = false;
    if (typeof savedChesscom !== 'undefined' || typeof savedLichess !== 'undefined') {
        const checkChesscom = typeof savedChesscom !== 'undefined' && savedChesscom && savedChesscom !== "None" && username.toLowerCase() === savedChesscom.toLowerCase();
        const checkLichess = typeof savedLichess !== 'undefined' && savedLichess && savedLichess !== "None" && username.toLowerCase() === savedLichess.toLowerCase();
        
        if (currentPlatform === 'chesscom' && checkChesscom) isMyProfile = true;
        if (currentPlatform === 'lichess' && checkLichess) isMyProfile = true;
    }

    const quickSwitchContainer = document.getElementById('quick-switch-container');
    const myGamesBtn = document.getElementById('my-games-btn');

    if (quickSwitchContainer && myGamesBtn) {
        if (isMyProfile) {
            quickSwitchContainer.style.display = ''; 
            myGamesBtn.style.display = 'none'; 

            const quickChesscom = document.getElementById('quick-chesscom');
            const quickLichess = document.getElementById('quick-lichess');
            if (quickChesscom && quickLichess) {
                if (currentPlatform === 'chesscom') {
                    quickChesscom.classList.add('bg-yellow-500/20', 'text-yellow-500');
                    quickChesscom.classList.remove('text-slate-500');
                    quickLichess.classList.remove('bg-yellow-500/20', 'text-yellow-500');
                    quickLichess.classList.add('text-slate-500');
                } else {
                    quickLichess.classList.add('bg-yellow-500/20', 'text-yellow-500');
                    quickLichess.classList.remove('text-slate-500');
                    quickChesscom.classList.remove('bg-yellow-500/20', 'text-yellow-500');
                    quickChesscom.classList.add('text-slate-500');
                }
            }
        } else {
            quickSwitchContainer.style.display = 'none'; 
            myGamesBtn.style.display = 'flex'; 
        }
    }

    // ==========================================
    // CACHE INTERCEPTOR
    // ==========================================
    if (!forceRefresh && typeof savedPlatformData !== 'undefined' && savedPlatformData[currentPlatform] && savedPlatformData[currentPlatform].username.toLowerCase() === username.toLowerCase()) {
        const cache = savedPlatformData[currentPlatform];
        
        // Restore state from memory
        allGamesCache = cache.allGamesCache;
        availableArchives = cache.availableArchives;
        archiveIndex = cache.archiveIndex;
        currentUserCache = cache.currentUserCache;
        
        // Swap UI instantly (Safely)
        document.getElementById('import-view')?.classList.add('hidden');
        document.getElementById('games-list-view')?.classList.remove('hidden');
        document.getElementById('main-header')?.classList.add('hidden');
        
        // Render from memory and exit function
        refreshGameList();
        return;
    }
    // ==========================================

    const btn = document.getElementById('fetch-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('btn-loader');
    const errorDiv = document.getElementById('error-msg');

    // Reset State
    allGamesCache = [];
    currentGamesList = [];
    availableArchives = [];
    archiveIndex = 0;
    currentOffset = 0;
    currentUserCache = username;
    isLoading = false;

    // UI Loading State (Safely)
    if (btn) {
        btn.disabled = true;
        btn.classList.add('opacity-75');
    }
    if (btnText) btnText.innerText = "Searching...";
    if (loader) loader.classList.remove('hidden');
    if (errorDiv) errorDiv.classList.add('hidden');
    
    const gamesContainer = document.getElementById('games-container');
    if (gamesContainer) gamesContainer.innerHTML = ''; 

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
        
        // --- SAVE NEW SEARCH TO CACHE ---
        if (typeof savedPlatformData !== 'undefined') {
            savedPlatformData[currentPlatform] = {
                username: username,
                allGamesCache: [...allGamesCache],
                availableArchives: [...availableArchives],
                archiveIndex: archiveIndex,
                currentUserCache: currentUserCache
            };
        }
        // --------------------------------

        // Safely manipulate UI elements
        document.getElementById('import-view')?.classList.add('hidden');
        document.getElementById('games-list-view')?.classList.remove('hidden');
        document.getElementById('main-header')?.classList.add('hidden'); 
        
        renderNextBatch();

    } catch (err) {
        // Safely show error
        if (errorDiv) {
            errorDiv.innerText = err.message;
            errorDiv.classList.remove('hidden');
        }
        
        // Safely manipulate UI elements
        document.getElementById('dashboard-view')?.classList.add('hidden');
        document.getElementById('games-list-view')?.classList.add('hidden');
        document.getElementById('import-view')?.classList.remove('hidden');
        document.getElementById('main-header')?.classList.remove('hidden');
        
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
    
    // Keep the cache continuously updated as you scroll back in time
    if (typeof savedPlatformData !== 'undefined' && savedPlatformData['chesscom']) {
        savedPlatformData['chesscom'].allGamesCache = [...allGamesCache];
        savedPlatformData['chesscom'].archiveIndex = archiveIndex;
    }
    
    return true; 
}

async function renderNextBatch() {
    if (isLoading) return;
    isLoading = true;

    const loader = document.getElementById('scroll-loader');
    const container = document.getElementById('games-container');
    
    // Safely remove hidden class if loader exists
    loader?.classList.remove('hidden');

    if (currentOffset + BATCH_SIZE >= allGamesCache.length) {
        await fetchNextMonth();
    }

    setTimeout(() => {
        // Re-fetch elements in case the user navigated away during the timeout or fetchNextMonth
        const currentContainer = document.getElementById('games-container');
        const currentLoader = document.getElementById('scroll-loader');
        
        if (!currentContainer) {
            isLoading = false;
            return;
        }
        
        if (currentOffset >= allGamesCache.length) {
            currentLoader?.classList.add('hidden');
            isLoading = false;
            return;
        }

        const batch = allGamesCache.slice(currentOffset, currentOffset + BATCH_SIZE);
        appendGamesToDOM(batch);
        currentOffset += BATCH_SIZE;
        
        currentLoader?.classList.add('hidden');
        isLoading = false;

        // Use currentContainer to safely check scroll height
        if (currentContainer.scrollHeight <= currentContainer.clientHeight && currentOffset < allGamesCache.length) {
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
    
    if (!btn) return; 

    btn.disabled = false;
    btn.classList.remove('opacity-75');
    if (btnText) btnText.innerText = "Find Games";
    if (loader) loader.classList.add('hidden');
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
    if (tcBox) {
        tcBox.innerText = game.time_class;
        const timeColorClass = TIME_STYLES[game.time_class] || 'text-slate-400';
        tcBox.className = `flex items-center justify-center px-4 rounded-md bg-slate-800 border border-slate-700 font-bold text-xs uppercase tracking-wider ${timeColorClass}`;
    }
    
    document.getElementById('games-list-view')?.classList.add('hidden');
    document.getElementById('import-view')?.classList.add('hidden');
    document.getElementById('dashboard-view')?.classList.remove('hidden');

    initChessBoard(pgn); 
    if (board) board.orientation(userSide);
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
        
        // --- SAFETY CHECK: Did the user navigate away during the await? ---
        const canvasExists = document.getElementById('evalChart');
        if (!canvasExists) {
            return; // Abort silently if the UI is gone
        }
        
        if (currentAnalysisData && currentAnalysisData.position_metrics) {
            initEvalChart(currentAnalysisData.position_metrics);
            updateBoard(); 
        }

        if (loader) {
            loader.classList.add('opacity-0');
            setTimeout(() => loader?.classList.add('hidden'), 500); 
        }
        if (content) {
            setTimeout(() => {
                content?.classList.remove('opacity-0');
                content?.classList.add('opacity-100');
            }, 300);
        }

    } catch (e) {
        console.error("Analysis Failed:", e);
        // Only show alert and reset if they haven't navigated away
        if (document.getElementById('dashboard-view')) {
            alert("Error: " + e.message);
            resetView();
        }
    }
}

// Scroll handler for the games container
function handleGamesScroll(element) {
    const { scrollTop, scrollHeight, clientHeight } = element;
    // Trigger when within 50px of the bottom
    if (scrollTop + clientHeight >= scrollHeight - 50) {
        renderNextBatch();
    }
}