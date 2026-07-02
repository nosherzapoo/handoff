const GITHUB_OWNER  = 'nosherzapoo';
const GITHUB_REPO   = 'OSBdata';
const WORKFLOW_FILE = 'ny-gaming-manual.yml';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const email = (req.body?.email || '').trim().toLowerCase();

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email address' });
  }

  if (!process.env.GITHUB_TOKEN) {
    return res.status(500).json({ error: 'GITHUB_TOKEN not configured on server' });
  }

  const ghRes = await fetch(
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
        'Accept':        'application/vnd.github.v3+json',
        'Content-Type':  'application/json',
        'User-Agent':    'ny-gaming-vercel',
      },
      body: JSON.stringify({ ref: 'main', inputs: { recipient_email: email } }),
    }
  );

  if (ghRes.status === 204) return res.status(200).json({ success: true });

  const errText = await ghRes.text();
  return res.status(500).json({ error: `GitHub API error ${ghRes.status}: ${errText}` });
}
