#!/usr/bin/env node
// Reconcile an Actual Budget account against a transactions.json produced by
// csv_to_transactions.py. Requires @actual-app/api (see SKILL.md for
// install). Destructive by design (deletes existing transactions before
// re-importing the full history) — refuses to touch anything without
// --confirm. An agent's command-approval layer will likely gate the actual
// delete/insert call on top of that. Both are features, not bugs: don't try
// to route around either.
//
// Usage:
//   node reconcile_actual.mjs --list-accounts
//   node reconcile_actual.mjs --inspect <account-id>
//   node reconcile_actual.mjs --account-id <id> --transactions transactions.json [--confirm]
//
// Server auth: --server-pw-file <path> or $ACTUAL_API_PASSWORD
// E2E auth:    --e2e-pw-file <path>    or $ACTUAL_E2E_PASSWORD
// Server URL:  --server-url <url>      or $ACTUAL_SERVER_URL

import * as api from '@actual-app/api';
import fs from 'node:fs';

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : def;
}
function flag(name) {
  return process.argv.includes(name);
}

const serverUrl = arg('--server-url', process.env.ACTUAL_SERVER_URL || 'https://actual.loup-peluso.com');
const serverPwFile = arg('--server-pw-file');
const e2ePwFile = arg('--e2e-pw-file');
const serverPassword = serverPwFile ? fs.readFileSync(serverPwFile, 'utf8').trim() : process.env.ACTUAL_API_PASSWORD;
const e2ePassword = e2ePwFile ? fs.readFileSync(e2ePwFile, 'utf8').trim() : process.env.ACTUAL_E2E_PASSWORD;
const dataDir = arg('--data-dir', './budget-cache');

if (!serverPassword) {
  console.error('ERROR: no server password. Pass --server-pw-file or set $ACTUAL_API_PASSWORD (see actual-budget/secrets.enc.env in iac-stacks).');
  process.exit(1);
}

fs.mkdirSync(dataDir, { recursive: true });
await api.init({ dataDir, serverURL: serverUrl, password: serverPassword });

const budgets = await api.getBudgets();
if (budgets.length === 0) {
  console.error('ERROR: no budgets visible to this server account.');
  process.exit(1);
}
await api.downloadBudget(budgets[0].groupId, e2ePassword ? { password: e2ePassword } : {});

if (flag('--list-accounts')) {
  const accounts = await api.getAccounts();
  for (const a of accounts) {
    console.log(`${a.id}  ${a.offbudget ? '[off-budget]' : '[on-budget] '}  ${a.name}`);
  }
  await api.shutdown();
  process.exit(0);
}

const accountId = arg('--account-id') || arg('--inspect');
if (!accountId) {
  console.error('ERROR: need --account-id (or --list-accounts / --inspect <id>).');
  await api.shutdown();
  process.exit(1);
}

const existing = await api.getTransactions(accountId, '2000-01-01', '2100-01-01');
const sumAll = existing.reduce((s, t) => s + t.amount, 0);
const sumCleared = existing.filter(t => t.cleared).reduce((s, t) => s + t.amount, 0);
const uncleared = existing.filter(t => !t.cleared);
console.log(`existing: ${existing.length} transactions, sum=${(sumAll/100).toFixed(2)} (cleared only: ${(sumCleared/100).toFixed(2)})`);
if (uncleared.length) {
  console.log(`  ${uncleared.length} uncleared (pending) transaction(s):`);
  for (const t of uncleared) console.log(`    ${t.date}  ${(t.amount/100).toFixed(2)}  ${t.notes || t.imported_payee || ''}`);
}

if (flag('--inspect')) {
  await api.shutdown();
  process.exit(0);
}

const txnPath = arg('--transactions');
if (!txnPath) {
  console.error('ERROR: need --transactions <path to transactions.json>.');
  await api.shutdown();
  process.exit(1);
}
const { opening, transactions, meta } = JSON.parse(fs.readFileSync(txnPath, 'utf8'));
const toInsert = [opening, ...transactions];
const targetCents = meta.target_cents;

console.log(`\nplan: delete ${existing.length} existing transaction(s), insert ${toInsert.length} `
  + `(1 opening balance of ${(opening.amount/100).toFixed(2)} + ${transactions.length} history), `
  + `final balance -> ${(targetCents/100).toFixed(2)}`);

if (!flag('--confirm')) {
  console.log('\nDRY RUN — nothing changed. Re-run with --confirm to execute.');
  await api.shutdown();
  process.exit(0);
}

console.log('\ndeleting existing transactions...');
for (const t of existing) await api.deleteTransaction(t.id);

console.log('inserting reconciled history...');
const result = await api.addTransactions(accountId, toInsert, { learnCategories: false, runTransfers: false });
console.log('addTransactions result:', result);

const final = await api.getTransactions(accountId, '2000-01-01', '2100-01-01');
const finalSum = final.reduce((s, t) => s + t.amount, 0);
console.log(`\nFINAL: ${final.length} transactions, sum=${finalSum} cents = ${(finalSum/100).toFixed(2)} EUR`);
if (finalSum !== targetCents) {
  console.error(`WARNING: final sum does not match target (${(targetCents/100).toFixed(2)})!`);
  process.exitCode = 3;
}

await api.shutdown();
