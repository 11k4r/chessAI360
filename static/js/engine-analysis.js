function createDeepWorker() {
    return new Worker('/static/stockfish17/stockfish.js');
}


function executeTask(worker, task) {
    return new Promise((resolve) => {
        let currentLines = {};
        let topLines = [];
        
        let stockfishFen = task.fen;

        let engineWatchdog = setTimeout(() => {
            worker.onmessage = null;
            resolve(null); 
        }, 25000);

        worker.onmessage = (e) => {
            const msg = e.data;
            if (typeof msg !== 'string') return;
            
            // Parse info strings for evaluation and PV
            if (msg.startsWith('info') && msg.includes('score') && msg.includes('pv')) {
                let multipv = 1;
                const pvMatch = msg.match(/multipv (\d+)/);
                if (pvMatch) multipv = parseInt(pvMatch[1]);

                let score = 0;
                let isMate = false;
                let mateMoves = 0;

                if(msg.includes('cp')) {
                    const match = msg.match(/cp (-?\d+)/);
                    if(match) score = parseInt(match[1]);
                } else if (msg.includes('mate')) {
                    const match = msg.match(/mate (-?\d+)/);
                    if(match) {
                        isMate = true;
                        mateMoves = parseInt(match[1]);
                    }
                }

                if (isMate) {
                    let actualMate = mateMoves * task.perspective;
                    score = actualMate > 0 ? `M${Math.abs(actualMate)}` : `-M${Math.abs(actualMate)}`;
                } else {
                    score = score * task.perspective;
                }

                const pvIndex = msg.indexOf(' pv ');
                let bestMoveLan = "";
                let fullPv = ""; 
                
                if (pvIndex !== -1) {
                    fullPv = msg.substring(pvIndex + 4).trim();
                    bestMoveLan = fullPv.split(' ')[0];
                }

                currentLines[multipv] = { 
                    rank: multipv, 
                    eval: score, 
                    move: bestMoveLan, 
                    line: fullPv 
                };
            }
            
            // Bestmove signals the engine is done searching
            if (msg.startsWith('bestmove')) {
                topLines = Object.values(currentLines).sort((a,b) => a.rank - b.rank).slice(0, 3);
                
                clearTimeout(engineWatchdog);
                worker.onmessage = null;
                
                resolve({
                    ply: task.ply,
                    move_played: task.movePlayedLAN,
                    fen: stockfishFen,
                    deep_eval: topLines.length > 0 ? topLines[0].eval : 0.0,
                    top_lines: topLines
                });
            }
        };

        // Kick off Deep Engine
        worker.postMessage('setoption name MultiPV value 3');
        worker.postMessage(task.movesString);
        // Assumes SEARCH_DEPTH is defined globally somewhere else in your code
        worker.postMessage(`go depth ${SEARCH_DEPTH}`); 
    });
}

async function processSingleGameInParallel(pgn) {
    const chess = new Chess();
    if (!chess.load_pgn(pgn)) return [];
    
    const history = chess.history({ verbose: true });
    let tasks = [];
    
    let currentMoves = [];
    const replayBoard = new Chess();
    
    // 1. Manually add the starting position (Ply 0)
    tasks.push({
        ply: 0,
        movesString: "position startpos",
        movePlayedLAN: null,
        perspective: 1, // White to move
        fen: replayBoard.fen()
    });

    // 2. Add every subsequent position
    for(let i=0; i < history.length; i++) {
        const m = history[i];
        const currentLan = m.from + m.to + (m.promotion || '');
        
        currentMoves.push(currentLan);
        replayBoard.move(m);
        
        tasks.push({
            ply: i + 1,
            movesString: "position startpos moves " + currentMoves.join(" "),
            movePlayedLAN: currentLan,
            perspective: (i % 2 === 0) ? -1 : 1, // If White just moved (even index), it is Black's turn (-1)
            fen: replayBoard.fen()
        });
    }

    let results = [];
    let currentTaskIndex = 0;
    let completedTasks = 0; 
    
    // workerRoutine now accepts a single worker rather than a workerPair
    const workerRoutine = async (worker) => {
        while (true) {
            let taskIndex = currentTaskIndex++;
            if (taskIndex >= tasks.length) break;
            
            const task = tasks[taskIndex];
            const result = await executeTask(worker, task);
            if (result) results.push(result);

            completedTasks++;
            const loaderText = document.getElementById('loader-text');
            if (loaderText) {
                loaderText.innerText = `Analyzing Position ${completedTasks} / ${tasks.length}`;
            }
        }
    };

    // Assumes workerPool is now populated just by createDeepWorker() instances
    await Promise.all(workerPool.map(w => workerRoutine(w)));
    
    // Ensure chronological order
    results.sort((a, b) => a.ply - b.ply);
    return results;
}