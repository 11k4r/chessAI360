function createClassicalWorker() {
    const baseUrl = new URL('/static/stockfish11/', window.location.href).href;
    const scriptUrl = baseUrl + 'stockfish.js'; 

    const workerSource = `
        var Module = {
            locateFile: function(path) {
                if (path.indexOf('http') === 0) return path;
                return '${baseUrl}' + path;
            },
            mainScriptUrlOrBlob: '${scriptUrl}'
        };
        
        var pendingMessages = [];
        var engineInstance = null;

        self.onmessage = function(event) {
            if (engineInstance) {
                engineInstance.postMessage(event.data);
            } else {
                pendingMessages.push(event.data);
            }
        };

        importScripts('${scriptUrl}');

        if (typeof Stockfish !== 'undefined') {
            Stockfish(Module).then(sf => {
                engineInstance = sf;
                sf.addMessageListener(function(line) {
                    self.postMessage(line);
                });
                while (pendingMessages.length > 0) {
                    sf.postMessage(pendingMessages.shift());
                }
            }).catch(err => console.error(err));
        }
    `;

    const blob = new Blob([workerSource], { type: 'application/javascript' });
    return new Worker(URL.createObjectURL(blob));
}

function createDeepWorker() {
    return new Worker('/static/stockfish17/stockfish.js');
}

function calculatePhase(fen) {
    if (!fen) return 0;
    
    const phaseWeights = {
        'n': 1, 'b': 1, 'r': 2, 'q': 4,
        'N': 1, 'B': 1, 'R': 2, 'Q': 4
    };
    
    // 1. Isolate the board layout part of the FEN
    const boardState = fen.split(' ')[0];
    let currentPhase = 0;
    
    // 2. Sum the weights of all pieces currently on the board
    for (let char of boardState) {
        if (phaseWeights[char]) {
            currentPhase += phaseWeights[char];
        }
    }
    
    // 3. Cap at 24 and scale to Stockfish's 0-128 range
    currentPhase = Math.min(currentPhase, 24);
    return Math.floor((currentPhase * 128) / 24);
}

function executeTask(workerPair, task) {
    return new Promise((resolve) => {
        const cw = workerPair.classical;
        const dw = workerPair.deep;
        
        let staticTrace = null;
        let currentPhase = 0;                     
        let currentLines = {};
        let topLines = [];
		
		let stockfishFen = task.fen;

        let cwPhase = 'static_eval';
        let dwPhase = 'nnue_best'; 
        let dwTaskDone = false;
        let cwTasksDone = false;

        let cwEvalQueue = [];
        let currentCwTask = null;
        let cwEvalBuffer = "";               

        let engineWatchdog = setTimeout(() => {
            cw.onmessage = null; dw.onmessage = null;
            resolve(null); 
        }, 25000);

        function checkCompletion() {
            if (dwTaskDone && cwTasksDone) {
                clearTimeout(engineWatchdog);
                cw.onmessage = null;
                dw.onmessage = null;
                
                resolve({
                    ply: task.ply,
                    move_played: task.movePlayedLAN,
                    fen: stockfishFen,
                    phase: currentPhase,
                    deep_eval: topLines.length > 0 ? topLines[0].eval : 0.0,
                    top_lines: topLines, 
                    static_eval_trace: staticTrace
                });
            }
        }

        function parseCwBuffer(buffer) {
            const match = buffer.match(/Fen:\s+(.+)/);
            const fen = match ? match[1].trim() : null;
            return { fen, eval: buffer.trim() };
        }

        function processNextCwQueue() {
            if (cwEvalQueue.length > 0) {
                currentCwTask = cwEvalQueue.shift();
                cwEvalBuffer = ""; 
                
                cw.postMessage(currentCwTask.moves);
                cw.postMessage('d');     
                cw.postMessage('eval');
                cw.postMessage('isready');
            } else {
                currentCwTask = null; 
                if (dwTaskDone) {
                    cwTasksDone = true;
                    checkCompletion();
                }
            }
        }

        cw.onmessage = (e) => {
            const msg = e.data;
            if (typeof msg !== 'string') return;
            
            if (cwPhase === 'static_eval') {
                if (!msg.startsWith('info') && !msg.startsWith('bestmove') && !msg.startsWith('option')) {
                    cwEvalBuffer += msg + "\n";
                }
                if (msg.startsWith('bestmove')) {
                    const parsed = parseCwBuffer(cwEvalBuffer);
                    staticTrace = parsed.eval;
					if (parsed.fen) stockfishFen = parsed.fen;
                    currentPhase = calculatePhase(parsed.fen || task.fen); 
                    
                    cwPhase = 'queue_processing';
                    
                    // Trigger Deep Engine now that Classical has parsed the root
                    dwPhase = 'nnue_best';
                    dw.postMessage('setoption name MultiPV value 3');
                    dw.postMessage(task.movesString);
                    dw.postMessage(`go depth ${SEARCH_DEPTH}`);
                }
            } 
            else if (cwPhase === 'queue_processing') {
                if (msg === 'readyok') {
                    const parsed = parseCwBuffer(cwEvalBuffer);
                    
                    if (currentCwTask && currentCwTask.type === 'top_leaf') {
                        topLines[currentCwTask.index].leaf_static_eval_trace = parsed.eval;
                        topLines[currentCwTask.index].leaf_fen = parsed.fen;
                        topLines[currentCwTask.index].leaf_phase = calculatePhase(parsed.fen);
                    }
                    processNextCwQueue(); 
                } else {
                    cwEvalBuffer += msg + "\n";
                }
            }
        };

        dw.onmessage = (e) => {
            const msg = e.data;
            if (typeof msg !== 'string') return;
            
            if (dwPhase === 'nnue_best') {
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
                
                if (msg.startsWith('bestmove')) {
                    topLines = Object.values(currentLines).sort((a,b) => a.rank - b.rank).slice(0, 3);
                    dwTaskDone = true;
                    
                    // Queue leaves of the top 3 lines for Classical eval
                    topLines.forEach((line, index) => {
                        cwEvalQueue.push({
                            type: 'top_leaf',
                            index: index,
                            moves: `${task.movesString} ${line.line}`
                        });
                    });
                    
                    if (currentCwTask === null) {
                        processNextCwQueue();
                    }
                }
            }
        };

        // Kick off Classical Engine
        cwEvalBuffer = "";
        cw.postMessage(task.movesString);
        cw.postMessage('d'); 
        cw.postMessage('eval');
        cw.postMessage('go nodes 1');
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
    
    const workerRoutine = async (workerPair) => {
        while (true) {
            let taskIndex = currentTaskIndex++;
            if (taskIndex >= tasks.length) break;
            
            const task = tasks[taskIndex];
            const result = await executeTask(workerPair, task);
            if (result) results.push(result);

            completedTasks++;
            const loaderText = document.getElementById('loader-text');
            if (loaderText) {
                loaderText.innerText = `Analyzing Position ${completedTasks} / ${tasks.length}`;
            }
        }
    };

    await Promise.all(workerPool.map(w => workerRoutine(w)));
    
    // Ensure chronological order
    results.sort((a, b) => a.ply - b.ply);
    return results;
}