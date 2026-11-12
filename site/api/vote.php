<?php
declare(strict_types=1);

// Voting API for the name-day calendar: which name should be the headline of a day.
//
//   GET  vote.php            -> {"days": {"MM-DD": {"Name": votes}}, "mine": {"MM-DD": "Name"}}
//   POST vote.php {day,name} -> same shape, after recording the vote
//
// Storage is one JSON file guarded by flock. The shared hosting gives us PHP but no
// managed database, and 366 days x a few names stays tiny, so a file is enough and
// keeps deploys to a plain FTPS upload.

const STORE_DIR = __DIR__ . '/store';
const VOTES_FILE = STORE_DIR . '/votes.json';
const SALT_FILE = STORE_DIR . '/salt.txt';
const NAMES_FILE = __DIR__ . '/../data/names.json';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function fail(int $code, string $message): never
{
    http_response_code($code);
    echo json_encode(['error' => $message], JSON_UNESCAPED_UNICODE);
    exit;
}

// One vote per day per visitor. We keep only a salted hash of the IP address, never
// the address itself; the salt is generated on the server and is not in the repo,
// so the hashes cannot be reversed by anyone who only has the votes file.
function voterId(): string
{
    if (!is_file(SALT_FILE)) {
        file_put_contents(SALT_FILE, bin2hex(random_bytes(32)), LOCK_EX);
    }
    $salt = trim((string) file_get_contents(SALT_FILE));
    return substr(hash('sha256', $salt . ($_SERVER['REMOTE_ADDR'] ?? '')), 0, 20);
}

function respond(array $votes, string $voter): never
{
    $days = [];
    $mine = [];
    foreach ($votes as $day => $ballots) {
        foreach ($ballots as $who => $name) {
            $days[$day][$name] = ($days[$day][$name] ?? 0) + 1;
            if ($who === $voter) {
                $mine[$day] = $name;
            }
        }
    }
    echo json_encode(['days' => (object) $days, 'mine' => (object) $mine], JSON_UNESCAPED_UNICODE);
    exit;
}

if (!is_dir(STORE_DIR) && !mkdir(STORE_DIR, 0755, true)) {
    fail(500, 'store unavailable');
}
$handle = fopen(VOTES_FILE, 'c+');
if ($handle === false) {
    fail(500, 'store unavailable');
}
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
flock($handle, $method === 'POST' ? LOCK_EX : LOCK_SH);
$votes = json_decode((string) stream_get_contents($handle), true) ?: [];
$voter = voterId();

if ($method === 'GET') {
    flock($handle, LOCK_UN);
    respond($votes, $voter);
}
if ($method !== 'POST') {
    fail(405, 'method not allowed');
}

// Browsers always send Origin on cross-site POSTs; rejecting foreign origins stops
// other websites from casting votes through their visitors.
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '' && parse_url($origin, PHP_URL_HOST) !== explode(':', $_SERVER['HTTP_HOST'] ?? '')[0]) {
    fail(403, 'foreign origin');
}
$body = json_decode((string) file_get_contents('php://input'), true);
$day = is_array($body) ? (string) ($body['day'] ?? '') : '';
$name = is_array($body) ? (string) ($body['name'] ?? '') : '';

// Only names the calendar already lists for that day are votable. Free-text
// suggestions would need moderation, which a site without accounts cannot do.
$data = json_decode((string) file_get_contents(NAMES_FILE), true);
$allowed = array_column($data['days'][$day]['candidates'] ?? [], 0);
if (!in_array($name, $allowed, true)) {
    fail(400, 'unknown day or name');
}

$votes[$day][$voter] = $name;   // voting again on the same day replaces the old vote
rewind($handle);
ftruncate($handle, 0);
fwrite($handle, json_encode($votes, JSON_UNESCAPED_UNICODE));
fflush($handle);
flock($handle, LOCK_UN);
respond($votes, $voter);
