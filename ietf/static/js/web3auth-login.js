document.addEventListener('DOMContentLoaded', function() {
    // Web3Auth login handlers
    const googleLoginBtn = document.getElementById('google-login');
    const walletLoginBtn = document.getElementById('wallet-login');
    const twitterLoginBtn = document.getElementById('twitter-login');
    const emailLoginBtn = document.getElementById('email-login');

    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/auth/web3auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        verifierId: 'google_' + Date.now(),
                        typeOfLogin: 'google',
                        email: 'test@example.com',
                        name: 'Test User',
                        profileImage: 'https://example.com/avatar.jpg',
                        evmAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e'
                    })
                });

                if (response.ok) {
                    window.location.href = '/'; // Redirect to home
                } else {
                    const error = await response.json();
                    alert('Login failed: ' + (error.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Login error:', error);
                alert('Login error: ' + error.message);
            }
        });
    }

    if (walletLoginBtn) {
        walletLoginBtn.addEventListener('click', async function() {
            try {
                const walletAddress = '0x' + Math.random().toString(16).substr(2, 40);
                const response = await fetch('/api/auth/web3auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        verifierId: 'wallet_' + walletAddress,
                        typeOfLogin: 'wallet',
                        evmAddress: walletAddress
                    })
                });

                if (response.ok) {
                    window.location.href = '/'; // Redirect to home
                } else {
                    const error = await response.json();
                    alert('Wallet connection failed: ' + (error.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Wallet error:', error);
                alert('Wallet connection error: ' + error.message);
            }
        });
    }

    if (twitterLoginBtn) {
        twitterLoginBtn.addEventListener('click', function() {
            alert('X (Twitter) login will be implemented with real Web3Auth modal');
        });
    }

    if (emailLoginBtn) {
        emailLoginBtn.addEventListener('click', function() {
            alert('Email login will be implemented with real Web3Auth modal');
        });
    }
});

// Utility function for copying wallet addresses
function copyWalletAddress(address) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(address).then(function() {
            // Simple feedback
            const badge = event.target;
            const originalText = badge.textContent;
            badge.textContent = 'Copied!';
            badge.style.background = 'var(--success-color, #00ba7c)';
            setTimeout(() => {
                badge.textContent = originalText;
                badge.style.background = '';
            }, 2000);
        }).catch(function(err) {
            console.error('Copy failed:', err);
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = address;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            document.body.removeChild(textArea);
            alert('Wallet address copied to clipboard!');
        } catch (err) {
            document.body.removeChild(textArea);
            alert('Failed to copy wallet address');
        }
    }
}