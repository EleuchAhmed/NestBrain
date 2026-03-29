import https from 'https';
import fs from 'fs';
import path from 'path';
import os from 'os';

function check() {
    const authPath = path.join(os.homedir(), ".notebooklm-mcp", "auth.json");
    if (!fs.existsSync(authPath)) {
        console.error("No auth.json found");
        return;
    }

    const data = JSON.parse(fs.readFileSync(authPath, "utf-8"));
    const cookies = Object.entries(data.cookies).map(([k, v]) => `${k}=${v}`).join("; ");

    console.log("Checking cookies length:", cookies.length);

    const options = {
        hostname: 'notebooklm.google.com',
        port: 443,
        path: '/',
        method: 'GET',
        headers: {
            'Cookie': cookies,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        },
        // manual redirect handle
    };

    const runReq = (opt: any) => {
        const req = https.request(opt, (res) => {
            console.log("Status Code:", res.statusCode);
            console.log("Location:", res.headers.location);
            if (res.statusCode === 302 && res.headers.location) {
                console.log("Following redirect to:", res.headers.location);
                const url = new URL(res.headers.location);
                const newOpt = {
                    ...opt,
                    hostname: url.hostname,
                    path: url.pathname + url.search,
                    headers: { ...opt.headers }
                };
                runReq(newOpt);
                return;
            }
            let body = '';
            res.on('data', (d) => { body += d; });
            res.on('end', () => {
                console.log("Response length:", body.length);
                const atMatch = body.match(/"SNlM0e":"([^"]+)"/);
                console.log("Extracted at token:", atMatch ? atMatch[1] : "NOT FOUND");
            });
        });
        req.on('error', (e) => { console.error(e); });
        req.end();
    };

    runReq(options);
}

check();
