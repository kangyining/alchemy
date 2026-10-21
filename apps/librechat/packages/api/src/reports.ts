import http from 'node:http';
import https from 'node:https';
import { createHash } from 'node:crypto';
import type { RequestHandler } from 'express';
import type { ServerRequest } from './types/http';

type Options = {
  target?: string;
  apiKey?: string;
  getAuthorization?: (audience: string) => Promise<string | null>;
};

type RunBody = { appName?: string; userId?: string; sessionId?: string };
const sessionPattern = /^[a-zA-Z0-9_-]{1,128}$/;

export function createReportProxy({ target, apiKey, getAuthorization }: Options): RequestHandler {
  return async (req, res) => {
    const user = (req as ServerRequest).user;
    if (!user?.id) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }
    if (!target || !apiKey) {
      res.status(503).json({ error: 'Report service authentication is not configured' });
      return;
    }
    const userId = `u_${createHash('sha256')
      .update(`${user.tenantId ?? ''}\0${user.id}`)
      .digest('hex')}`;
    const scopedSession = (id: string) =>
      `s_${createHash('sha256').update(`${userId}\0${id}`).digest('hex')}`;
    let parsed: URL;
    let parts: string[];
    try {
      parsed = new URL(target);
      if (
        parsed.protocol !== 'https:' &&
        !(
          parsed.protocol === 'http:' &&
          ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname)
        )
      ) {
        throw new Error('Invalid target');
      }
      parts = new URL(req.url, 'http://proxy.local').pathname
        .split('/')
        .filter(Boolean)
        .map(decodeURIComponent);
      if (parts.some((part) => part === '.' || part === '..' || /[/\\\0]/.test(part))) {
        throw new Error('Invalid path');
      }
    } catch {
      res.status(400).json({ error: 'Invalid report request' });
      return;
    }
    const owned = (id: string) => id === 'me' || id === userId;
    let body = req.body as RunBody | undefined;
    if (parts[0] === 'reports' && parts.length >= 2 && parts.length <= 3 && req.method === 'GET') {
      if (!owned(parts[1])) {
        res.status(403).json({ error: 'Report owner mismatch' });
        return;
      }
      parts[1] = userId;
    } else if (
      parts[0] === 'apps' &&
      parts[1] === 'report_agents' &&
      parts[2] === 'users' &&
      parts[4] === 'sessions' &&
      parts.length === 6 &&
      ['GET', 'POST', 'DELETE'].includes(req.method) &&
      sessionPattern.test(parts[5])
    ) {
      if (!owned(parts[3])) {
        res.status(403).json({ error: 'Session owner mismatch' });
        return;
      }
      parts[3] = userId;
      parts[5] = scopedSession(parts[5]);
      if (req.method === 'POST') {
        body = {};
      }
    } else if (
      parts.length === 1 &&
      ['run', 'run_sse'].includes(parts[0]) &&
      req.method === 'POST'
    ) {
      if (
        !body ||
        body.appName !== 'report_agents' ||
        !body.userId ||
        !owned(body.userId) ||
        !body.sessionId ||
        !sessionPattern.test(body.sessionId)
      ) {
        res.status(403).json({ error: 'Invalid report identity or session' });
        return;
      }
      body = { ...body, userId, sessionId: scopedSession(body.sessionId) };
    } else {
      res.status(404).json({ error: 'Unsupported report route' });
      return;
    }
    try {
      const headers: http.OutgoingHttpHeaders = {
        'X-API-Key': apiKey,
        'X-Report-User': userId,
        'Content-Type': 'application/json',
        Accept: req.headers.accept ?? '*/*',
      };
      if (parsed.protocol === 'https:') {
        const authorization = await getAuthorization?.(target);
        if (!authorization) {
          res.status(502).json({ error: 'Report service credentials unavailable' });
          return;
        }
        headers.Authorization = authorization;
      }
      const payload = req.method === 'POST' ? JSON.stringify(body ?? {}) : undefined;
      if (payload) {
        headers['Content-Length'] = Buffer.byteLength(payload);
      }
      const transport = parsed.protocol === 'https:' ? https : http;
      const upstream = transport.request(
        {
          protocol: parsed.protocol,
          hostname: parsed.hostname,
          port: parsed.port,
          path: `/${parts.map(encodeURIComponent).join('/')}`,
          method: req.method,
          headers,
        },
        (response) => {
          res.status(response.statusCode ?? 502);
          for (const header of ['content-type', 'content-disposition', 'cache-control']) {
            const value = response.headers[header];
            if (value) {
              res.setHeader(header, value);
            }
          }
          res.setHeader('Cache-Control', 'no-store');
          response.pipe(res);
        },
      );
      upstream.setTimeout(60 * 60 * 1000, () => upstream.destroy(new Error('Report timeout')));
      upstream.on('error', () => {
        if (!res.headersSent) {
          res.status(502).json({ error: 'Report service unavailable' });
        } else {
          res.end();
        }
      });
      res.on('close', () => upstream.destroy());
      upstream.end(payload);
    } catch {
      res.status(502).json({ error: 'Report service unavailable' });
    }
  };
}
