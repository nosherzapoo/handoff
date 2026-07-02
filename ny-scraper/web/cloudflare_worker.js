/**
 * NY Gaming Data — Cloudflare Worker
 *
 * Paste this into the Cloudflare Worker editor and click Save & Deploy.
 * Then: Settings → Variables → Secrets → add GITHUB_TOKEN = your PAT
 * After adding the secret, click Save & Deploy again to bind it.
 */

addEventListener('fetch', function(event) {
  event.respondWith(
    handleRequest(event.request).catch(function(err) {
      // Catch-all: always return JSON with CORS headers, even on crashes
      return new Response(JSON.stringify({ error: 'Worker error: ' + err.message }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    })
  );
});

async function handleRequest(request) {
  var cors = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  // Handle CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: cors });
  }

  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
    });
  }

  // Parse email from request body
  var email;
  try {
    var body = await request.json();
    email = (body.email || '').trim().toLowerCase();
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
    });
  }

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return new Response(JSON.stringify({ error: 'Invalid email address' }), {
      status: 400,
      headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
    });
  }

  // Check that GITHUB_TOKEN secret is bound
  if (typeof GITHUB_TOKEN === 'undefined') {
    return new Response(JSON.stringify({ error: 'GITHUB_TOKEN secret not configured. Add it under Settings → Variables in the Cloudflare dashboard, then redeploy.' }), {
      status: 500,
      headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
    });
  }

  // Trigger GitHub Actions workflow
  var ghRes = await fetch(
    'https://api.github.com/repos/nosherzapoo/OSBdata/actions/workflows/ny-gaming-manual.yml/dispatches',
    {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + GITHUB_TOKEN,
        'Accept':        'application/vnd.github.v3+json',
        'Content-Type':  'application/json',
        'User-Agent':    'ny-gaming-worker',
      },
      body: JSON.stringify({ ref: 'main', inputs: { recipient_email: email } }),
    }
  );

  if (ghRes.status === 204) {
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
    });
  }

  var errBody = await ghRes.text();
  return new Response(JSON.stringify({ error: 'GitHub API error ' + ghRes.status + ': ' + errBody }), {
    status: 500,
    headers: Object.assign({ 'Content-Type': 'application/json' }, cors),
  });
}
