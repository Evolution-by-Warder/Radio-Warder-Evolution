# Run locally in PowerShell with GitHub CLI authenticated as Evolution-by-Warder.
$ErrorActionPreference = 'Stop'
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'Install GitHub CLI first, then run this script again.'
}
$radioRepository = 'Evolution-by-Warder/Radio-Warder-Evolution'
$radioDescription = 'Warder Radio - native Enigma2 internet radio for OpenATV and OpenPLi, with picons, favourites, history, optional recording, 21 languages, last-station resume and verified automatic updates.'
& gh repo edit $radioRepository --description $radioDescription --homepage 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases' --add-topic 'enigma2,radio,openatv,openpli,python,picons,internet-radio'
if ($LASTEXITCODE -ne 0) { throw 'GitHub repository metadata was not updated.' }
& gh repo view $radioRepository --json nameWithOwner,description,url
if ($LASTEXITCODE -ne 0) { throw 'Could not verify the GitHub repository metadata.' }
