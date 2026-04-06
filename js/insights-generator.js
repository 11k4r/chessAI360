
// ==========================================
// 4. Data Fetching & Limiting
// ==========================================
// ==========================================
// 4. Data Fetching & Limiting
// ==========================================
async function fetchAllGames(chesscomUser, lichessUser) {
    const cutoffMs = Date.now() - (360 * 24 * 60 * 60 * 1000);
    const cutoffSec = Math.floor(cutoffMs / 1000);
    const payload = { chesscom: {}, lichess: {} };

    // --- Chess.com ---
    if (chesscomUser && chesscomUser.trim() !== "") {
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
    }

    // --- Lichess ---
    if (lichessUser && lichessUser.trim() !== "") {
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
		const profileRes = await fetch(`/api/chesscom/profile/${chesscomUser}`); 
        if (profileRes.ok) {
            const profile = await profileRes.json();
            
            const usernameEl = document.getElementById('player-username');
            if (usernameEl) usernameEl.innerText = profile.username || username;
            
            if (profile.avatar) {
                const imgEl = document.getElementById('player-img');
                if (imgEl) imgEl.src = profile.avatar;
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

            const rapidEl = document.getElementById('rating-rapid');
            const blitzEl = document.getElementById('rating-blitz');
            const bulletEl = document.getElementById('rating-bullet');

            if (rapidEl) rapidEl.innerText = rapidRating;
            if (blitzEl) blitzEl.innerText = blitzRating;
            if (bulletEl) bulletEl.innerText = bulletRating;
        }
    } catch (e) {
        console.error("Failed to fetch profile info:", e);
    }
}
