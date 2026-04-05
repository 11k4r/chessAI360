
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
            timestamp: timestamp,
			platform: platform
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

var userRatingsCache = window.userRatingsCache || {
    chesscom: { rapid: 0, blitz: 0, bullet: 0 },
    lichess: { rapid: 0, blitz: 0, bullet: 0 }
};
window.userRatingsCache = userRatingsCache;

window.updateRatingDisplay = function(platformFilter) {
    let rapid = 0, blitz = 0, bullet = 0;
    let countRapid = 0, countBlitz = 0, countBullet = 0;

    if (platformFilter === 'all' || platformFilter === 'chesscom') {
        if (userRatingsCache.chesscom.rapid) { rapid += userRatingsCache.chesscom.rapid; countRapid++; }
        if (userRatingsCache.chesscom.blitz) { blitz += userRatingsCache.chesscom.blitz; countBlitz++; }
        if (userRatingsCache.chesscom.bullet) { bullet += userRatingsCache.chesscom.bullet; countBullet++; }
    }
    if (platformFilter === 'all' || platformFilter === 'lichess') {
        if (userRatingsCache.lichess.rapid) { rapid += userRatingsCache.lichess.rapid; countRapid++; }
        if (userRatingsCache.lichess.blitz) { blitz += userRatingsCache.lichess.blitz; countBlitz++; }
        if (userRatingsCache.lichess.bullet) { bullet += userRatingsCache.lichess.bullet; countBullet++; }
    }

    const rapidEl = document.getElementById('rating-rapid');
    const blitzEl = document.getElementById('rating-blitz');
    const bulletEl = document.getElementById('rating-bullet');

    if (rapidEl) rapidEl.innerText = countRapid > 0 ? Math.round(rapid / countRapid) : '?';
    if (blitzEl) blitzEl.innerText = countBlitz > 0 ? Math.round(blitz / countBlitz) : '?';
    if (bulletEl) bulletEl.innerText = countBullet > 0 ? Math.round(bullet / countBullet) : '?';
};

async function fetchAndPaintProfile(chesscomUser, lichessUser, platformFilter = 'all') {
    try {
        // Fetch Chess.com Data
        if (chesscomUser) {
            const profileRes = await fetch(`https://api.chess.com/pub/player/${chesscomUser}`);
            if (profileRes.ok) {
                const profile = await profileRes.json();
                
                const usernameEl = document.getElementById('player-username');
                if (usernameEl && platformFilter !== 'lichess') usernameEl.innerText = profile.username || chesscomUser;
                
                if (profile.avatar) {
                    const imgEl = document.getElementById('player-img');
                    if (imgEl && platformFilter !== 'lichess') imgEl.src = profile.avatar;
                }
                if (profile.title) {
                    const badge = document.getElementById('title-badge');
                    if (badge && platformFilter !== 'lichess') {
                        badge.innerText = profile.title;
                        badge.classList.remove('hidden');
                    }
                }
                if (profile.country) {
                    const countryCode = profile.country.split('/').pop().toLowerCase();
                    const flagImg = document.getElementById('country-flag');
                    if (flagImg && countryCode && platformFilter !== 'lichess') flagImg.src = `https://flagcdn.com/w40/${countryCode}.png`;
                }
            }

            const statsRes = await fetch(`https://api.chess.com/pub/player/${chesscomUser}/stats`);
            if (statsRes.ok) {
                const stats = await statsRes.json();
                userRatingsCache.chesscom.rapid = stats.chess_rapid?.last?.rating || 0;
                userRatingsCache.chesscom.blitz = stats.chess_blitz?.last?.rating || 0;
                userRatingsCache.chesscom.bullet = stats.chess_bullet?.last?.rating || 0;
            }
        }

        // Fetch Lichess Data
        if (lichessUser) {
            const lichessRes = await fetch(`https://lichess.org/api/user/${lichessUser}`);
            if (lichessRes.ok) {
                const profile = await lichessRes.json();
                
                // If only Lichess is provided/filtered, use its profile info
                if ((!chesscomUser || platformFilter === 'lichess') && document.getElementById('player-username')) {
                    document.getElementById('player-username').innerText = profile.username;
                }
                
                userRatingsCache.lichess.rapid = profile.perfs?.rapid?.rating || 0;
                userRatingsCache.lichess.blitz = profile.perfs?.blitz?.rating || 0;
                userRatingsCache.lichess.bullet = profile.perfs?.bullet?.rating || 0;
            }
        }

        updateRatingDisplay(platformFilter);

    } catch (e) {
        console.error("Failed to fetch profile info:", e);
    }
}