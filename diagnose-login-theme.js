#!/usr/bin/env node

/**
 * DIAGNOSTIC: Login Page Theme Issue
 * Checks why login page appears white instead of dark
 */

const fs = require('fs');
const path = require('path');

// Read the main application file
const appFile = path.join(__dirname, 'ietf_data_viewer_simple.py');
const content = fs.readFileSync(appFile, 'utf8');

console.log('🔍 LOGIN PAGE THEME DIAGNOSTIC');
console.log('================================\n');

// Check 1: Login route theme setting
console.log('1. LOGIN ROUTE THEME SETTING:');
const loginRouteMatch = content.match(/@app\.route\('\/login\/'.*?def login\(\):.*?(current_theme = '[^']*')/s);
if (loginRouteMatch) {
    console.log(`   ✅ Found: ${loginRouteMatch[1]}`);
} else {
    console.log('   ❌ Could not find login route theme setting');
}

// Check 2: BASE_TEMPLATE data-theme attribute
console.log('\n2. BASE_TEMPLATE DATA-THEME:');
const baseTemplateMatch = content.match(/BASE_TEMPLATE = """(.*?)"""([\s\S]*?)html lang="en" data-theme="\{theme\}"/);
if (baseTemplateMatch) {
    console.log('   ✅ Found data-theme="{theme}" in BASE_TEMPLATE');
} else {
    console.log('   ❌ Could not find data-theme in BASE_TEMPLATE');
}

// Check 3: Theme JavaScript logic
console.log('\n3. THEME JAVASCRIPT LOGIC:');
const jsThemeMatch = content.match(/const userTheme = html\.getAttribute\('data-theme'\) \|\| 'dark';/);
if (jsThemeMatch) {
    console.log('   ✅ Found userTheme fallback to "dark"');
} else {
    console.log('   ❌ Could not find userTheme logic');
}

const savedThemeMatch = content.match(/const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' \?/);
if (savedThemeMatch) {
    console.log('   ✅ Found savedTheme logic with localStorage fallback');
} else {
    console.log('   ❌ Could not find savedTheme logic');
}

// Check 4: Theme CSS variables
console.log('\n4. THEME CSS VARIABLES:');
const lightThemeMatch = content.match(/:root \{\{\s*\/\*\s*Light theme/);
const darkThemeMatch = content.match(/\[data-theme="dark"\] \{\{\s*\/\*\s*Dark theme/);
if (lightThemeMatch && darkThemeMatch) {
    console.log('   ✅ Found both light and dark theme CSS definitions');
} else {
    console.log('   ❌ Missing theme CSS definitions');
}

// Check 5: Web3Auth modal theme
console.log('\n5. WEB3AUTH MODAL THEME:');
const modalThemeMatch = content.match(/theme: 'dark'/);
if (modalThemeMatch) {
    console.log('   ✅ Web3Auth modal set to dark theme');
} else {
    console.log('   ❌ Web3Auth modal theme not set to dark');
}

// Check 6: Modal bypass issue
console.log('\n6. MODAL BYPASS DIAGNOSIS:');
const connectCallMatch = content.match(/web3auth\.connect\(\)/);
if (connectCallMatch) {
    console.log('   ⚠️  web3auth.connect() called without parameters - this opens modal with all options');
    console.log('   💡 User expects modal first, then select Google');
} else {
    console.log('   ❌ Could not find web3auth.connect() call');
}

console.log('\n🔧 RECOMMENDED FIXES:');
console.log('1. Login page: Check browser dev tools for data-theme attribute');
console.log('2. Modal bypass: Consider adding intermediate modal or changing UX flow');
console.log('3. Test: Add console.log to JavaScript theme loading');

console.log('\n📋 QUICK TEST:');
console.log('Run this in browser console on login page:');
console.log('console.log("data-theme:", document.documentElement.getAttribute("data-theme"));');
console.log('console.log("CSS vars:", getComputedStyle(document.documentElement).getPropertyValue("--bg-color"));');