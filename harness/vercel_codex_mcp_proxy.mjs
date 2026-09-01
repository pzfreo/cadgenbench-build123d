#!/usr/bin/env node
/**
 * Compatibility shim for Codex namespace tools through non-OpenAI Responses
 * providers. Codex emits MCP tools as proprietary `type: "namespace"`
 * containers; Vercel/Gemini expects standard top-level function tools.
 *
 * This loopback-only proxy flattens each namespace tool on the request and
 * restores namespace/name fields on function-call response items so Codex can
 * dispatch them to its MCP runtime. It never logs request bodies or headers.
 */

import fs from "node:fs";
import http from "node:http";

const UPSTREAM = "https://ai-gateway.vercel.sh/codex/v1";
const MAX_GATEWAY_ATTEMPTS = 6;

function option(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const portFile = option("--port-file");
const logFile = option("--log-file");
if (!portFile || !logFile) {
  throw new Error("usage: vercel_codex_mcp_proxy.mjs --port-file FILE --log-file FILE");
}

function log(message) {
  fs.appendFileSync(logFile, `${new Date().toISOString()} ${message}\n`);
}

function flatToolName(namespace, toolName) {
  return `${namespace}__${toolName}`;
}

function flattenTools(payload) {
  const callMap = new Map();
  let namespaceCount = 0;
  const flattened = [];

  for (const spec of payload.tools ?? []) {
    if (
      spec?.type !== "namespace" ||
      spec.name !== "mcp__build123d" ||
      !Array.isArray(spec.tools)
    ) {
      flattened.push(spec);
      continue;
    }

    namespaceCount += 1;
    for (const tool of spec.tools) {
      if (tool?.type !== "function" || typeof tool.name !== "string") {
        continue;
      }
      const name = flatToolName(spec.name, tool.name);
      callMap.set(name, { namespace: spec.name, name: tool.name });
      flattened.push({ ...tool, name });
    }
  }

  return {
    payload: { ...payload, tools: flattened },
    callMap,
    namespaceCount,
  };
}

function restoreCalls(value, callMap) {
  if (Array.isArray(value)) {
    return value.map((item) => restoreCalls(item, callMap));
  }
  if (!value || typeof value !== "object") {
    return value;
  }

  const restored = {};
  for (const [key, child] of Object.entries(value)) {
    restored[key] = restoreCalls(child, callMap);
  }
  if (typeof restored.name === "string" && callMap.has(restored.name)) {
    const mapped = callMap.get(restored.name);
    restored.name = mapped.name;
    restored.namespace = mapped.namespace;
  }
  return restored;
}

function upstreamHeaders(headers) {
  const blocked = new Set([
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "accept-encoding",
  ]);
  return Object.fromEntries(
    Object.entries(headers).filter(([name]) => !blocked.has(name.toLowerCase())),
  );
}

function downstreamHeaders(headers) {
  const blocked = new Set([
    "content-length",
    "content-encoding",
    "connection",
    "transfer-encoding",
  ]);
  return Object.fromEntries(
    [...headers.entries()].filter(([name]) => !blocked.has(name.toLowerCase())),
  );
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function relaySse(upstream, response, callMap) {
  const decoder = new TextDecoder();
  let pending = "";

  for await (const chunk of upstream.body) {
    pending += decoder.decode(chunk, { stream: true });
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    for (let line of lines) {
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line.startsWith("data: ") && line !== "data: [DONE]") {
        try {
          const event = JSON.parse(line.slice(6));
          line = `data: ${JSON.stringify(restoreCalls(event, callMap))}`;
        } catch {
          // Preserve non-JSON SSE data exactly.
        }
      }
      response.write(`${line}\n`);
    }
  }

  pending += decoder.decode();
  if (pending) response.write(pending);
  response.end();
}

const server = http.createServer(async (request, response) => {
  if (request.method !== "POST" || request.url !== "/responses") {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: "unsupported proxy route" }));
    return;
  }

  try {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const incoming = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    const transformed = flattenTools(incoming);
    log(
      `request namespaces=${transformed.namespaceCount} flattened=${transformed.callMap.size}`,
    );

    const upstreamBody = JSON.stringify(transformed.payload);
    let upstream;
    let bufferedBody;
    for (let attempt = 1; attempt <= MAX_GATEWAY_ATTEMPTS; attempt += 1) {
      try {
        upstream = await fetch(`${UPSTREAM}${request.url}`, {
          method: "POST",
          headers: upstreamHeaders(request.headers),
          body: upstreamBody,
        });
      } catch (error) {
        if (attempt === MAX_GATEWAY_ATTEMPTS) throw error;
        log(`retry transient_gateway_fetch_error attempt=${attempt}`);
        await delay(Math.min(500 * 2 ** (attempt - 1), 5000));
        continue;
      }
      if (upstream.ok) break;

      bufferedBody = await upstream.text();
      const retryableGatewayFailure = [
        "Service temporarily unavailable",
        "NGHTTP2_ENHANCE_YOUR_CALM",
        "Cannot connect to API",
      ].some((marker) => bufferedBody.includes(marker));
      if (!retryableGatewayFailure || attempt === MAX_GATEWAY_ATTEMPTS) break;
      log(`retry transient_gateway_failure attempt=${attempt}`);
      bufferedBody = undefined;
      await delay(Math.min(500 * 2 ** (attempt - 1), 5000));
    }
    if (!upstream) throw new Error("gateway request did not run");
    log(`response status=${upstream.status}`);
    response.writeHead(upstream.status, downstreamHeaders(upstream.headers));

    const contentType = upstream.headers.get("content-type") ?? "";
    if (contentType.includes("text/event-stream") && upstream.body) {
      await relaySse(upstream, response, transformed.callMap);
      return;
    }

    const body = bufferedBody ?? (await upstream.text());
    try {
      response.end(JSON.stringify(restoreCalls(JSON.parse(body), transformed.callMap)));
    } catch {
      response.end(body);
    }
  } catch (error) {
    log(`proxy_error ${error instanceof Error ? error.message : String(error)}`);
    if (!response.headersSent) {
      response.writeHead(502, { "content-type": "application/json" });
    }
    response.end(JSON.stringify({ error: "gateway compatibility proxy failed" }));
  }
});

server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("failed to obtain loopback proxy address");
  }
  fs.writeFileSync(portFile, `${address.port}\n`, { mode: 0o600 });
  log(`listening port=${address.port}`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
