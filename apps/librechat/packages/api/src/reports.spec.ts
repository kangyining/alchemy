import http from 'node:http';
import express from 'express';
import request from 'supertest';
import { createHash } from 'node:crypto';
import type { AddressInfo } from 'node:net';
import { createReportProxy } from './reports';

const owner = `u_${createHash('sha256').update('tenant\0alice').digest('hex')}`;
const session = `s_${createHash('sha256').update(`${owner}\0fixture`).digest('hex')}`;

describe('authenticated report gateway', () => {
  let backend: http.Server;
  let target: string;
  const seen: { path: string; user?: string; key?: string; cookie?: string; body: string }[] = [];

  beforeAll(async () => {
    backend = http.createServer((req, res) => {
      let body = '';
      req.on('data', (chunk: Buffer) => {
        body += chunk.toString();
      });
      req.on('end', () => {
        seen.push({
          path: req.url ?? '',
          user: req.headers['x-report-user']?.toString(),
          key: req.headers['x-api-key']?.toString(),
          cookie: req.headers.cookie,
          body,
        });
        if (req.url === '/run_sse') {
          res.setHeader('Content-Type', 'text/event-stream');
          res.end('data: {"status":"completed"}\n\n');
        } else if (req.url?.endsWith('.pdf')) {
          res.setHeader('Content-Type', 'application/pdf');
          res.end('%PDF-synthetic');
        } else {
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify([{ status: 'completed' }]));
        }
      });
    });
    await new Promise<void>((resolve) => backend.listen(0, '127.0.0.1', resolve));
    target = `http://127.0.0.1:${(backend.address() as AddressInfo).port}`;
  });

  afterAll(async () => {
    await new Promise<void>((resolve, reject) =>
      backend.close((error) => (error ? reject(error) : resolve())),
    );
  });

  function app(apiKey: string | undefined = 'synthetic-service-key') {
    const instance = express();
    instance.use((req, _res, next) => {
      if (req.headers['x-test-user'] === 'alice') {
        req.user = { id: 'alice', tenantId: 'tenant' } as NonNullable<typeof req.user>;
      }
      next();
    });
    instance.use(
      '/report-agent-api',
      express.json({ limit: '1kb' }),
      createReportProxy({ target, apiKey }),
    );
    return instance;
  }

  test('rejects anonymous, foreign-owner, unconfigured, and unsupported requests', async () => {
    const count = seen.length;
    await request(app()).get('/report-agent-api/reports/me').expect(401);
    await request(app())
      .get('/report-agent-api/reports/victim')
      .set('X-Test-User', 'alice')
      .expect(403);
    await request(app(''))
      .get('/report-agent-api/reports/me')
      .set('X-Test-User', 'alice')
      .expect(503);
    await request(app()).get('/report-agent-api/apps').set('X-Test-User', 'alice').expect(404);
    await request(app())
      .post('/report-agent-api/run_sse')
      .set('X-Test-User', 'alice')
      .send({ appName: 'report_agents', userId: 'victim', sessionId: 'fixture' })
      .expect(403);
    expect(seen).toHaveLength(count);
  });

  test('binds uploads, session paths, streaming, history, and downloads to the verified user', async () => {
    await request(app())
      .post('/report-agent-api/apps/report_agents/users/me/sessions/fixture')
      .set('X-Test-User', 'alice')
      .set('Cookie', 'private=never-forward')
      .set('X-Report-User', 'forged')
      .send({ state: { malicious: true } })
      .expect(200);
    expect(seen.at(-1)).toMatchObject({
      path: `/apps/report_agents/users/${owner}/sessions/${session}`,
      user: owner,
      key: 'synthetic-service-key',
      body: '{}',
      cookie: undefined,
    });
    const stream = await request(app())
      .post('/report-agent-api/run_sse')
      .set('X-Test-User', 'alice')
      .send({
        appName: 'report_agents',
        userId: 'me',
        sessionId: 'fixture',
        newMessage: { parts: [{ inlineData: { data: 'c3ludGhldGlj' } }] },
      })
      .expect(200);
    expect(stream.text).toContain('data: {"status":"completed"}');
    expect(JSON.parse(seen.at(-1)?.body ?? '{}')).toMatchObject({
      userId: owner,
      sessionId: session,
      newMessage: { parts: [{ inlineData: { data: 'c3ludGhldGlj' } }] },
    });
    await request(app())
      .get('/report-agent-api/reports/me')
      .set('X-Test-User', 'alice')
      .expect(200);
    expect(seen.at(-1)?.path).toBe(`/reports/${owner}`);
    await request(app())
      .get('/report-agent-api/reports/me/fixture.pdf')
      .set('X-Test-User', 'alice')
      .expect('Content-Type', 'application/pdf')
      .expect(200);
    await request(app())
      .post('/report-agent-api/run_sse')
      .set('X-Test-User', 'alice')
      .send({ large: 'x'.repeat(2048) })
      .expect(413);
  });
});
