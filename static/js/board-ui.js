var isPawnInsightsActive = false;
var isSafetyInsightsActive = false;


var boardConfig = {
    start: () => { jumpToMove(0); },
    end: () => { jumpToMove(gameHistory.length - 1); },
    prev: () => { if (currentMoveIndex > 0) jumpToMove(currentMoveIndex - 1); },
    next: () => { if (currentMoveIndex < gameHistory.length - 1) jumpToMove(currentMoveIndex + 1); },
    flip: () => { 
        if(board) {
            board.flip();
            updatePlayerInfo();
        }
    }
};

function jumpToMove(index) {
    currentMoveIndex = index;
    updateBoard();
}

function initChessBoard(pgn) {
    const chess = new Chess();
    if (!chess.load_pgn(pgn)) return;
    
    gameHistory = [];
    sanHistory = []; 
    
    const replay = new Chess();
    gameHistory.push(replay.fen()); 
    sanHistory.push("Start"); 
    
    const history = chess.history({ verbose: true });
    
    history.forEach((m, i) => {
        replay.move(m);
        gameHistory.push(replay.fen());
        
        const moveNumber = Math.floor(i / 2) + 1;
        const isWhite = (i % 2 === 0);
        const label = isWhite 
            ? `${moveNumber}. ${m.san}`
            : `${moveNumber}... ${m.san}`;
            
        sanHistory.push(label);
    });
    
    currentMoveIndex = 0; 

    if (board) board.destroy();
    
    board = Chessboard('board', {
        position: 'start',
        draggable: false, 
        pieceTheme: '/static/images/chesspieces/{piece}.png'
    });
}

function updateBoard() {
    if (!gameHistory[currentMoveIndex]) return;
    
    // 1. Update the physical board and FEN
    const fullFen = gameHistory[currentMoveIndex];
    const piecesOnlyFen = fullFen.split(' ')[0];
    board.position(piecesOnlyFen, true);
    
    const fenBox = document.getElementById('fen-box');
    if(fenBox) fenBox.value = fullFen; 

    // 2. Update player clocks and names
    updatePlayerInfo(); 

    // 3. Update the analysis metrics
    if (currentAnalysisData && currentAnalysisData.position_metrics) {
        
        // Thanks to the refactor, currentMoveIndex perfectly matches the array index!
        const metrics = currentAnalysisData.position_metrics[currentMoveIndex];
        
        if (metrics) {
            // Update the Eval Box directly
            updateEvalUI(metrics.eval, metrics.eval_text); 
            
            const descBox = document.getElementById('ai-description-box');
            if (descBox) descBox.innerText = metrics.description || "AI-powered commentary is coming soon. Pleasee note that we are still actively training our models and fine-tuning the underlying position & game metrics.";

            // Move notation and classification
            document.getElementById('stat-move').innerText = currentMoveIndex === 0 ? '-' : (sanHistory[currentMoveIndex] || '-');
            document.getElementById('stat-class').innerText = metrics.move_classification || '-';
            
            // Move Accuracy
            let accuracyText = '-';
            if (metrics.move_accuracy && currentMoveIndex !== 0) {
                accuracyText = (metrics.move_accuracy * 100).toFixed(1) + '%';
            } else if (currentMoveIndex === 0) {
                accuracyText = '0%';
            }
            document.getElementById('stat-accuracy').innerText = accuracyText;
            
            // Time Management
			document.getElementById('stat-time').innerText = (metrics.time !== undefined && metrics.time !== null) ? metrics.time + 's' : '-';
            document.getElementById('stat-time-class').innerText = metrics.time_classification || '-';
            
            // Classification Colors
            const classEl = document.getElementById('stat-class');
            classEl.className = 'text-sm font-bold truncate w-full text-white'; // Reset to default
            const cls = metrics.move_classification;
            
            if (['Brilliant', 'Great'].includes(cls)) classEl.classList.add('text-cyan-400');
            else if (cls === 'Best') classEl.classList.add('text-green-400');
            else if (['Excellent', 'Good'].includes(cls)) classEl.classList.add('text-green-300');
            else if (cls === 'Inaccuracy') classEl.classList.add('text-yellow-400');
            else if (cls === 'Mistake') classEl.classList.add('text-orange-400');
            else if (cls === 'Blunder') classEl.classList.add('text-red-500');
            
            // Expandable position breakdowns
            updateExpandedPositionMetrics(metrics);
        }
    }

    // 4. Update the Evaluation Chart dot indicator
    if (evalChartInstance) {
        const dataset = evalChartInstance.data.datasets[0];
        dataset.pointRadius = dataset.data.map((_, idx) => idx === currentMoveIndex ? 4 : 0);
        evalChartInstance.update('none'); 
    }
	
	if (isPawnInsightsActive && currentAnalysisData && currentAnalysisData.position_metrics) {
        drawPawnHighlights(currentAnalysisData.position_metrics[currentMoveIndex]);
    }
    if (isSafetyInsightsActive && currentAnalysisData && currentAnalysisData.position_metrics) {
        drawSafetyHighlights(currentAnalysisData.position_metrics[currentMoveIndex]);
    }
	
	// Auto-switch tabs based on the current move
    if (currentMoveIndex === 0) {
        // Reset the manual override when returning to the start
        userForcedTab = false; 
        
        if (currentActiveTab !== 'game') {
            switchAnalysisTab('game', false);
        }
    } else if (currentMoveIndex > 0) {
        // Only auto-switch to position if the user hasn't manually overridden it
        if (currentActiveTab !== 'position' && !userForcedTab) {
            switchAnalysisTab('position', false);
        }
    }
}

function resetView() {
	if (window.chessEngine) {
        window.chessEngine.cancelAnalysis();
    }
    document.getElementById('import-view').classList.remove('hidden');
    document.getElementById('main-header').classList.remove('hidden');
    document.getElementById('games-list-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('username-input').value = '';
    
    if(board) board.clear(); 
}

function setPlatform(platform) {
    currentPlatform = platform;
    const btnChesscom = document.getElementById('btn-chesscom');
    const btnLichess = document.getElementById('btn-lichess');

    if (platform === 'chesscom') {
        btnChesscom.className = "flex-1 pb-2 text-yellow-500 border-b-2 border-yellow-500 font-bold text-sm uppercase tracking-wider transition-all";
        btnLichess.className = "flex-1 pb-2 text-slate-600 font-bold text-sm uppercase tracking-wider hover:text-slate-400 transition-all";
    } else {
        btnLichess.className = "flex-1 pb-2 text-yellow-500 border-b-2 border-yellow-500 font-bold text-sm uppercase tracking-wider transition-all";
        btnChesscom.className = "flex-1 pb-2 text-slate-600 font-bold text-sm uppercase tracking-wider hover:text-slate-400 transition-all";
    }
}

function formatClock(seconds) {
    if (seconds === undefined || seconds === null) return '-';
    const s = Math.max(0, seconds);
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${r.toString().padStart(2, '0')}`;
}

function updatePlayerInfo() {
    if (!board) return;

    const orientation = board.orientation(); 
    const topEl = document.getElementById('player-top');
    const botEl = document.getElementById('player-bottom');

    let whiteTime = '-';
    let blackTime = '-';
    
    // Extract times from our new python dictionary structure
    if (currentAnalysisData && currentAnalysisData.position_metrics) {
        const metrics = currentAnalysisData.position_metrics[currentMoveIndex];
        
        if (metrics && metrics.time_remain) {
            whiteTime = formatClock(metrics.time_remain.white);
            blackTime = formatClock(metrics.time_remain.black);
        }
    }

    const getHtml = (name, elo, isWhite, clockStr) => `
        <div class="flex justify-between items-center w-full">
            <div class="flex items-center gap-3">
                <div class="w-3.5 h-3.5 rounded-full ${isWhite ? 'bg-slate-200' : 'bg-slate-900'} border-2 border-slate-500 shadow-sm flex-none"></div>
                <div class="font-bold text-white text-lg truncate max-w-[150px]">${name}</div>
                <div class="text-slate-500 text-xs font-mono bg-slate-800/80 border border-slate-700 px-2 py-0.5 rounded shadow-inner">${elo}</div>
            </div>
            <div class="font-mono text-lg font-bold ${clockStr === '-' ? 'text-slate-600' : 'text-slate-200'} bg-black/40 px-3 py-0.5 rounded border border-white/5 tracking-wider shadow-inner transition-colors">
                ${clockStr}
            </div>
        </div>
    `;

    const whiteName = gameHeaders.White || (currentGameInfo ? currentGameInfo.white.username : 'White');
    const whiteElo  = gameHeaders.WhiteElo || (currentGameInfo ? currentGameInfo.white.rating : '?');
    const blackName = gameHeaders.Black || (currentGameInfo ? currentGameInfo.black.username : 'Black');
    const blackElo  = gameHeaders.BlackElo || (currentGameInfo ? currentGameInfo.black.rating : '?');

    // Assign to Top/Bottom based on board flip orientation
    if (orientation === 'white') {
        topEl.innerHTML = getHtml(blackName, blackElo, false, blackTime);
        botEl.innerHTML = getHtml(whiteName, whiteElo, true, whiteTime);
    } else {
        topEl.innerHTML = getHtml(whiteName, whiteElo, true, whiteTime);
        botEl.innerHTML = getHtml(blackName, blackElo, false, blackTime);
    }
}

function initEvalChart(metrics) {
    const ctx = document.getElementById('evalChart').getContext('2d');
    if (evalChartInstance) evalChartInstance.destroy();
    
    // Fix: Remove the hardcoded 0.0. metrics[0] already contains Ply 0 natively now.
    const data = metrics.map(m => Math.max(-7, Math.min(7, m.eval)));
    const labels = data.map((_, i) => i);
    
    evalChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Advantage',
                data: data,
                borderColor: '#eab308', 
                backgroundColor: 'rgba(234, 179, 8, 0.15)',
                fill: true,
                tension: 0.3,
                borderWidth: 2,
                pointRadius: 0, // This gets dynamically updated in updateBoard()
                pointBackgroundColor: '#ffffff',
                pointBorderColor: '#ffffff',
                pointHitRadius: 15,
                pointHoverRadius: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: 6 },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    jumpToMove(elements[0].index); 
                }
            },
            scales: {
                y: { min: -7, max: 7, display: false },
                x: { display: false }
            },
            plugins: { 
                legend: { display: false },
                tooltip: { enabled: false } 
            },
            interaction: { mode: 'index', intersect: false }
        }
    });
}
function updateEvalUI(eval_val, eval_text) {
    const evalBox = document.getElementById('eval-box');
    if (!evalBox || eval_val === undefined) return;
    
    if (eval_text && eval_text.includes('M')) {
        evalBox.innerText = eval_text; 
    } else {
        let textVal = parseFloat(eval_val).toFixed(1);
        if (eval_val > 0) textVal = '+' + textVal;
        evalBox.innerText = textVal;
    }

    let intensity = Math.min(Math.abs(eval_val) / 5.0, 1.0);
    
    if (eval_val > 0) {
        let lightness = 40 + (intensity * 50); 
        evalBox.style.backgroundColor = `hsl(0, 0%, ${lightness}%)`;
        evalBox.style.color = lightness > 65 ? '#000' : '#fff';
    } else if (eval_val < 0) {
        let lightness = 40 - (intensity * 35); 
        evalBox.style.backgroundColor = `hsl(0, 0%, ${lightness}%)`;
        evalBox.style.color = '#fff';
    } else {
        evalBox.style.backgroundColor = ''; 
        evalBox.style.color = '';
    }
}

function copyFen() {
    const fenBox = document.getElementById('fen-box');
    const btn = fenBox.parentElement.nextElementSibling;
    const icon = btn.querySelector('i');
    
    if (fenBox.value === "Copied!") return;

    const originalFen = fenBox.value;

    navigator.clipboard.writeText(originalFen).then(() => {
        fenBox.value = "Copied!";
        fenBox.classList.remove('text-slate-400');
        fenBox.classList.add('text-green-400', 'text-center');
        
        icon.className = 'fa-solid fa-check text-green-400';
        
        setTimeout(() => {
            fenBox.value = gameHistory[currentMoveIndex]; 
            
            fenBox.classList.remove('text-green-400', 'text-center');
            fenBox.classList.add('text-slate-400');
            
            icon.className = 'fa-regular fa-copy';
        }, 1500);
    });
}

// Global Resize Handler
var lastWindowWidth = window.innerWidth;
var boardResizeTimeout;

window.addEventListener('resize', () => {
    clearTimeout(boardResizeTimeout);
    
    boardResizeTimeout = setTimeout(() => {
        if (window.innerWidth !== lastWindowWidth) {
            lastWindowWidth = window.innerWidth;
            if (board) {
                board.resize();
            }
        }
    }, 150);
});




// ==========================================
// EXPANDED POSITION METRICS
// ==========================================

function updateExpandedPositionMetrics(metrics) {
    if (!metrics) return;

    // 1. Strings
    const openingEl = document.getElementById('pos-exp-opening');
    const topLabelEl = document.getElementById('pos-exp-top-label');
    
    // Check if we are in the endgame to swap the title and text
    let topText = '-';
    if (metrics.phase && metrics.phase.toLowerCase() === 'endgame') {
        topLabelEl.innerText = 'Endgame';
        topText = metrics.endgame || '-';
    } else {
        topLabelEl.innerText = 'Opening';
        topText = metrics.opening || '-';
    }
    
    openingEl.innerText = topText;
    openingEl.title = topText; // Adds a hover tooltip in case it gets truncated

    // Dynamically shrink the font based on text length to fit the fixed container
    openingEl.className = "font-bold text-slate-200 text-center line-clamp-2 leading-tight"; // Base classes
    
    if (topText.length > 40) {
        openingEl.classList.add('text-[9px]'); // Extra small for huge names
    } else if (topText.length > 22) {
        openingEl.classList.add('text-[11px]'); // Medium small
    } else {
        openingEl.classList.add('text-sm'); // Normal size
    }

    document.getElementById('pos-exp-phase').innerText = metrics.phase || '-';
	
	document.getElementById('pos-exp-criticality').innerText = metrics.criticality !== undefined ? metrics.criticality : '-';
	
	document.getElementById('pos-exp-sharpness').innerText = metrics.sharpness !== undefined ? metrics.sharpness : '-';

    // 2. Top Lines
    const topLinesBox = document.getElementById('pos-exp-top-lines');
    if (topLinesBox) {
        if (metrics.top_lines && metrics.top_lines.length > 0) {
            topLinesBox.classList.remove('justify-center', 'items-center', 'text-slate-600');
            topLinesBox.innerHTML = '<div class="my-auto w-full">' + metrics.top_lines.map(line => {
                const evalText = typeof line.eval === 'number' && line.eval > 0 ? `+${line.eval}` : line.eval;
                const fullLine = line.line || '-';
                const displayText = line.display_text || fullLine; // Read the new display_text property
                
                return `
                <div class="flex justify-between items-center w-full mb-2 border-b border-slate-700/50 pb-1 last:border-0 last:mb-0 last:pb-0">
                    <span class="font-bold ${parseFloat(line.eval) >= 0 ? 'text-white' : 'text-slate-400'} flex-none whitespace-nowrap">${evalText}</span>
                    <span class="truncate ml-3 text-right text-slate-300 flex-1 min-w-0 cursor-help" 
                          data-line="${fullLine}"
                          onmouseenter="showLineTooltip(event, this.dataset.line)" 
                          onmousemove="moveLineTooltip(event)" 
                          onmouseleave="hideLineTooltip()">
                          ${displayText}
                    </span>
                </div>`;
            }).join('') + '</div>';
        } else {
            topLinesBox.classList.add('justify-center', 'items-center', 'text-slate-600');
            topLinesBox.innerHTML = '[ No lines available ]';
        }
    }

    // 3. Balance Bars
    // Mapping HTML ids to Python dictionary keys
    const barMappings = [
        { id: 'material', key: 'material' },
        { id: 'structure', key: 'pawn_structure' },
        { id: 'safety', key: 'king_safety' },
        { id: 'center', key: 'center_control' },
        { id: 'activity', key: 'activity' },
        { id: 'mobility', key: 'mobility' },
        { id: 'space', key: 'space' },
        { id: 'harmony', key: 'harmony' },
        { id: 'attack', key: 'attack' },
        { id: 'defence', key: 'defence' }
    ];

    barMappings.forEach(mapping => {
        const data = metrics[mapping.key];
        if (!data) return;

        let w = parseFloat(data.white) || 0;
        let b = parseFloat(data.black) || 0;
        
        // Calculate absolute magnitudes to determine bar share
        let absW = Math.max(0, w);
        let absB = Math.max(0, b);
        let total = absW + absB;
        
        let wPct = 50;
        let bPct = 50;
        
        if (total > 0) {
            wPct = (absW / total) * 100;
            bPct = (absB / total) * 100;
        }

        const whiteBar = document.getElementById(`bar-${mapping.id}-white`);
        const blackBar = document.getElementById(`bar-${mapping.id}-black`);
        
        if (whiteBar && blackBar) {
            whiteBar.style.width = `${wPct}%`;
            whiteBar.title = `White: ${w}`; 
            
            blackBar.style.width = `${bPct}%`;
            blackBar.title = `Black: ${b}`; 
        }
    });
}

// ==========================================
// CUSTOM TOOLTIP LOGIC
// ==========================================
function showLineTooltip(e, text) {
    const tooltip = document.getElementById('custom-line-tooltip');
    if (!tooltip || !text || text === '-') return;
    
    tooltip.innerText = text;
    tooltip.classList.remove('hidden');
    moveLineTooltip(e); // Position it instantly under the cursor
}

function moveLineTooltip(e) {
    const tooltip = document.getElementById('custom-line-tooltip');
    if (!tooltip || tooltip.classList.contains('hidden')) return;
    
    // Offset slightly from the cursor so it doesn't block the mouse
    let x = e.clientX + 15;
    let y = e.clientY + 15;

    // Prevent the tooltip from clipping off the right or bottom of the screen
    const rect = tooltip.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - 15;
    if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - 15;

    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

function hideLineTooltip() {
    const tooltip = document.getElementById('custom-line-tooltip');
    if (tooltip) tooltip.classList.add('hidden');
}




function backToGamesList() {
    // Stop the engine if it's running
    if (window.chessEngine) {
        window.chessEngine.cancelAnalysis();
    }
    
    isPawnInsightsActive = false;
    isSafetyInsightsActive = false;
    
    const pawnPanel = document.getElementById('pawn-insights-panel');
    const safetyPanel = document.getElementById('safety-insights-panel');
    
    if (pawnPanel) pawnPanel.classList.add('hidden');
    if (safetyPanel) safetyPanel.classList.add('hidden');
    
    if (typeof clearPawnHighlights === 'function') clearPawnHighlights();
    if (typeof clearSafetyHighlights === 'function') clearSafetyHighlights();
    // ------------------------------------------------
    
    // Hide the analysis dashboard, show the games list
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('games-list-view').classList.remove('hidden');
    
    if(board) board.clear(); 
}


// ==========================================
// PAWN INSIGHTS INTERACTIVITY
// ==========================================

function togglePawnInsights() {
    isPawnInsightsActive = !isPawnInsightsActive;
    const panel = document.getElementById('pawn-insights-panel');
    
    if (isPawnInsightsActive) {
        panel.classList.remove('hidden');
        
        // Initialize draggable on first open
        if (!panel.dataset.dragInit) {
            initDraggable('pawn-insights-header', 'pawn-insights-panel');
            panel.dataset.dragInit = 'true';
        }
        
        // Trigger draw using current move metrics
        if (currentAnalysisData && currentAnalysisData.position_metrics) {
            drawPawnHighlights(currentAnalysisData.position_metrics[currentMoveIndex]);
        }
    } else {
        panel.classList.add('hidden');
        clearPawnHighlights();
    }
}

function clearPawnHighlights() {
    $('.square-55d63')
        .removeClass('pawn-insight-active pawn-unstoppable pawn-protected-passer pawn-passer pawn-isolated pawn-doubled pawn-backward pawn-ram pawn-self-blocked')
        .removeAttr('title');
}

function drawPawnHighlights(metrics) {
    clearPawnHighlights();
    if (!metrics || !metrics.ai_features) return;

    const f = metrics.ai_features;
    const boardSquares = {}; 

    ['white', 'black'].forEach(color => {
        // Safe check in case the arrays are empty or undefined
        const getSquares = (key) => f[key] && f[key][color] ? f[key][color] : [];

        // 1. Board Highlights Priority using the NEW flat structure
        const traitMaps = [
            { path: getSquares('ram'), class: 'pawn-ram', title: 'Blocked Pawn (Ram)' },
            { path: getSquares('self_blocked'), class: 'pawn-self-blocked', title: 'Self-Blocked Pawn' },
            { path: getSquares('backward'), class: 'pawn-backward', title: 'Backward Pawn' },
            { path: getSquares('doubled'), class: 'pawn-doubled', title: 'Doubled Pawn' },
            { path: getSquares('isolated'), class: 'pawn-isolated', title: 'Isolated Pawn' },
            { path: getSquares('passed_pawn'), class: 'pawn-passer', title: 'Passed Pawn' },
            { path: getSquares('protected_passer'), class: 'pawn-protected-passer', title: 'Protected Passer' },
            { path: getSquares('unstoppable_passer'), class: 'pawn-unstoppable', title: 'Unstoppable Passer!' },
        ];

        traitMaps.forEach(trait => {
            if (trait.path && Array.isArray(trait.path)) {
                trait.path.forEach(sq => {
                    // Filter out pawn structure notations like 'ab' and ensure it's a valid square like 'a2'
                    if (sq.length === 2) {
                        if (!boardSquares[sq]) {
                            boardSquares[sq] = { classes: trait.class, titles: [trait.title] };
                        } else {
                            boardSquares[sq].classes = trait.class; 
                            if (!boardSquares[sq].titles.includes(trait.title)) {
                                boardSquares[sq].titles.push(trait.title); 
                            }
                        }
                    }
                });
            }
        });

        // 2. Update Overlay Panel Text
        const colorPrefix = color.charAt(0); 
        
        const islands = getSquares('pawn_island_shapes');
        document.getElementById(`pawn-insights-${colorPrefix}-islands`).innerText = `${islands.length} (${islands.join(', ')})`;
        
        // Majorities are returning empty arrays in your example dict, so we handle it gracefully
        const majs = getSquares('majority');
        document.getElementById(`pawn-insights-${colorPrefix}-majority`).innerText = majs.length > 0 ? majs.join(', ') : 'None';

        const shelterCount = f['shelter_count'] && f['shelter_count'][color] !== undefined ? f['shelter_count'][color] : 0;
        document.getElementById(`pawn-insights-${colorPrefix}-shelter`).innerText = shelterCount;

        const blockedCount = getSquares('ram').length + getSquares('self_blocked').length;
        document.getElementById(`pawn-insights-${colorPrefix}-blocked`).innerText = blockedCount;

        // Score 
        const score = metrics.pawn_structure[color] || 0;
        const scoreEl = document.getElementById(`pawn-insights-${colorPrefix}-score`);
        scoreEl.innerText = `${score > 0 ? '+' : ''}${score}`;
        scoreEl.className = `text-sm font-bold mb-2 ${score > 0 ? 'text-green-400' : (score < 0 ? 'text-red-400' : 'text-slate-400')}`;
    });

    // 3. Inject CSS classes
    Object.keys(boardSquares).forEach(sq => {
        const data = boardSquares[sq];
        const el = document.querySelector(`.square-${sq}`);
        if (el) {
            el.classList.add('pawn-insight-active', data.classes);
            el.title = data.titles.join(' + ');
        }
    });
}

function initDraggable(dragHeaderId, dragContainerId) {
    const header = document.getElementById(dragHeaderId);
    const container = document.getElementById(dragContainerId);
    let isDragging = false, startX, startY, startLeft, startTop;

    header.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = container.getBoundingClientRect();
        startLeft = rect.left;
        startTop = rect.top;
        document.body.classList.add('select-none'); // Prevent text highlighting while dragging
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    function onMouseMove(e) {
        if (!isDragging) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        container.style.left = `${startLeft + dx}px`;
        container.style.top = `${startTop + dy}px`;
        container.style.bottom = 'auto'; 
        container.style.right = 'auto';
    }

    function onMouseUp() {
        isDragging = false;
        document.body.classList.remove('select-none');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
}

// ==========================================
// KING SAFETY INSIGHTS INTERACTIVITY
// ==========================================

function toggleSafetyInsights() {
    if (isPawnInsightsActive) togglePawnInsights(); // Close Pawns if open
    
    isSafetyInsightsActive = !isSafetyInsightsActive;
    const panel = document.getElementById('safety-insights-panel');
    
    if (isSafetyInsightsActive) {
        panel.classList.remove('hidden');
        
        if (!panel.dataset.dragInit) {
            initDraggable('safety-insights-header', 'safety-insights-panel');
            panel.dataset.dragInit = 'true';
        }
        
        if (currentAnalysisData && currentAnalysisData.position_metrics) {
            drawSafetyHighlights(currentAnalysisData.position_metrics[currentMoveIndex]);
        }
    } else {
        panel.classList.add('hidden');
        clearSafetyHighlights();
    }
}

function clearSafetyHighlights() {
    $('.square-55d63')
        .removeClass('safety-insight-active safety-king-safe safety-king-danger safety-shield-intact safety-shield-pushed safety-zone-danger')
        .removeAttr('title');
}

function drawSafetyHighlights(metrics) {
    clearSafetyHighlights();
    if (!metrics || !metrics.ai_features) return;

    const f = metrics.ai_features;
    const boardSquares = {}; 

    ['white', 'black'].forEach(color => {
        const kingSq = f['king_sq'] && f['king_sq'][color] ? f['king_sq'][color] : null;
        if (!kingSq) return;

        const getSquares = (key) => f[key] && f[key][color] ? f[key][color] : [];
        const getVal = (key, fallback) => f[key] !== undefined && f[key][color] !== undefined ? f[key][color] : fallback;

        // 1. Determine overall danger
        const attackers = getVal('attackers_count', 0);
        const isOpen = getVal('open_file', false);
        const inDanger = attackers > 0 || isOpen;
        
        const kingClass = inDanger ? 'safety-king-danger' : 'safety-king-safe';
        boardSquares[kingSq] = { classes: kingClass, titles: [`${color === 'white' ? 'White' : 'Black'} King`] };

        // Add Zone Squares 
        if (attackers > 0) {
            getSquares('zone_squares').forEach(sq => {
                if (!boardSquares[sq]) {
                    boardSquares[sq] = { classes: 'safety-zone-danger', titles: ['Danger Zone'] };
                }
            });
        }

        // Add Shields
        getSquares('shield_rank_2').forEach(sq => {
            if (!boardSquares[sq]) boardSquares[sq] = { classes: 'safety-shield-intact', titles: ['Intact Shield'] };
        });
        getSquares('shield_rank_3').forEach(sq => {
            if (!boardSquares[sq]) boardSquares[sq] = { classes: 'safety-shield-pushed', titles: ['Weakened Shield'] };
        });

        // 2. Update Overlay Panel Text
        const colorPrefix = color.charAt(0);
        
        let fileStatus = "Closed";
        if (isOpen) fileStatus = "Open (Danger!)";
        else if (getVal('semi_open_file', false)) fileStatus = "Semi-Open";
        
        const fileEl = document.getElementById(`safety-insights-${colorPrefix}-file`);
        fileEl.innerText = fileStatus;
        fileEl.className = isOpen ? 'text-red-400 font-mono font-bold' : (getVal('semi_open_file', false) ? 'text-yellow-400 font-mono' : 'text-white font-mono');

        let shieldStatus = "Missing";
        const rank2Count = getSquares('shield_rank_2').length;
        const rank3Count = getSquares('shield_rank_3').length;
        if (rank2Count >= 2) shieldStatus = "Intact";
        else if (rank2Count + rank3Count >= 2) shieldStatus = "Pushed / Weakened";
        
        document.getElementById(`safety-insights-${colorPrefix}-shield`).innerText = shieldStatus;
        document.getElementById(`safety-insights-${colorPrefix}-attackers`).innerText = attackers;
        document.getElementById(`safety-insights-${colorPrefix}-shelter`).innerText = getVal('shelter_count', 0);

        // Score
        const score = metrics.king_safety[color] || 0;
        const scoreEl = document.getElementById(`safety-insights-${colorPrefix}-score`);
        scoreEl.innerText = `${score > 0 ? '+' : ''}${score}`;
        scoreEl.className = `text-sm font-bold mb-2 ${score > 0 ? 'text-green-400' : (score < 0 ? 'text-red-400' : 'text-slate-400')}`;
    });

    // 3. Inject CSS classes
    Object.keys(boardSquares).forEach(sq => {
        const data = boardSquares[sq];
        const el = document.querySelector(`.square-${sq}`);
        if (el) {
            el.classList.add('safety-insight-active', data.classes);
            if (!el.title) el.title = data.titles.join(' + ');
            else el.title += ' + ' + data.titles.join(' + ');
        }
    });
}


// ==========================================
// EXPANDED GAME METRICS
// ==========================================

function updateExpandedGameMetrics() {
    if (!currentAnalysisData || !currentAnalysisData.game_metrics) return;
    
    const gm = currentAnalysisData.game_metrics;

    // 1. Overview
    document.getElementById('game-exp-type').innerText = gm["Game Type"] || '-';
    document.getElementById('game-exp-volatility').innerText = gm.volatility ? gm.volatility.toFixed(2) : '-';

    // 2. Phase Accuracies & Missed Opportunities
    const phases = [
        { id: 'op', key: 'opening_acc' },
        { id: 'mg', key: 'middlegame_acc' },
        { id: 'eg', key: 'endgame_acc' }
    ];

    phases.forEach(phase => {
        if (gm[phase.key]) {
            document.getElementById(`game-exp-${phase.id}-w`).innerText = `${gm[phase.key].white || 0}%`;
            document.getElementById(`game-exp-${phase.id}-b`).innerText = `${gm[phase.key].black || 0}%`;
        }
    });

    if (gm.missed_opp) {
        document.getElementById('game-exp-miss-w').innerText = gm.missed_opp.white || 0;
        document.getElementById('game-exp-miss-b').innerText = gm.missed_opp.black || 0;
    }

    // 3. Playstyle Trait Bars
    const traits = ['tactics', 'strategy', 'intuition', 'calculation', 'time_management'];
    
    traits.forEach(trait => {
        if (gm[trait]) {
            let w = gm[trait].white || 0;
            let b = gm[trait].black || 0;
            
            // Calculate proportional width (out of total 100% combined, or max 100 each mapped to 50/50)
            let total = w + b;
            let wPct = 50;
            let bPct = 50;
            
            if (total > 0) {
                wPct = (w / total) * 100;
                bPct = (b / total) * 100;
            }

            const wBar = document.getElementById(`game-bar-${trait}-w`);
            const bBar = document.getElementById(`game-bar-${trait}-b`);
            
            if (wBar && bBar) {
                // Set the width and title
                wBar.style.width = `${wPct}%`;
                wBar.title = `White: ${w}`;
                bBar.style.width = `${bPct}%`;
                bBar.title = `Black: ${b}`;

                // Inject the actual values into the bars (hide if 0 to avoid clutter)
                wBar.innerText = w > 0 ? w : '';
                bBar.innerText = b > 0 ? b : '';
            }
        }
    });
}

var currentActiveTab = 'position'; // Track which tab is currently visible
var userForcedTab = false; // Track if the user manually clicked a tab

// Add the isManual parameter with a default of false
function switchAnalysisTab(tab, isManual = false) {
    if (isManual) {
        userForcedTab = true; // Disable auto-switching if the user clicked
    }
    
    currentActiveTab = tab;
    
    const posView = document.getElementById('expanded-position');
    const gameView = document.getElementById('expanded-game');
    const posBtn = document.getElementById('tab-btn-position');
    const gameBtn = document.getElementById('tab-btn-game');

    if (tab === 'position') {
        // Show Position View
        posView.classList.remove('hidden');
        posView.classList.add('flex');
        gameView.classList.add('hidden');
        gameView.classList.remove('flex');
        
        // Update Button Styling
        posBtn.className = "text-yellow-500 uppercase tracking-widest text-sm font-bold border-b-2 border-yellow-500 pb-1 transition-colors";
        gameBtn.className = "text-slate-500 hover:text-slate-300 uppercase tracking-widest text-sm font-bold border-b-2 border-transparent pb-1 transition-colors";
    } else {
        // Show Game View
        gameView.classList.remove('hidden');
        gameView.classList.add('flex');
        posView.classList.add('hidden');
        posView.classList.remove('flex');
        
        // Update Button Styling
        gameBtn.className = "text-yellow-500 uppercase tracking-widest text-sm font-bold border-b-2 border-yellow-500 pb-1 transition-colors";
        posBtn.className = "text-slate-500 hover:text-slate-300 uppercase tracking-widest text-sm font-bold border-b-2 border-transparent pb-1 transition-colors";
        
        // Ensure game data is loaded when tab is opened
        updateExpandedGameMetrics();
    }
}