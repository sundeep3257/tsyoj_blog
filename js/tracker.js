(function() {
    'use strict';
    
    let viewId = null;
    let articleViewId = null;
    let startTime = Date.now();
    let isArticlePage = false;
    let articleId = null;
    
    // Check if this is an article page
    const path = window.location.pathname;
    if (path.startsWith('/article/')) {
        isArticlePage = true;
        // Extract article ID from page - get it from data attribute
        const articleElement = document.querySelector('[data-article-id]');
        if (articleElement) {
            articleId = parseInt(articleElement.getAttribute('data-article-id'));
        }
    }
    
    // Start tracking
    function startTracking() {
        const path = window.location.pathname;
        const referrer = document.referrer || '';
        const userAgent = navigator.userAgent;
        
        fetch('/track/view/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                path: path,
                referrer: referrer,
                user_agent: userAgent
            }),
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            viewId = data.view_id;
        })
        .catch(error => {
            console.error('Tracking error:', error);
        });
        
        // Track article view if on article page
        if (isArticlePage && articleId) {
            fetch('/track/article/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    article_id: articleId
                }),
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                articleViewId = data.view_id;
            })
            .catch(error => {
                console.error('Article tracking error:', error);
            });
        }
    }
    
    // End tracking
    function endTracking() {
        if (!viewId) return;
        
        const duration = Math.floor((Date.now() - startTime) / 1000);
        
        // Use sendBeacon for reliability
        const data = JSON.stringify({
            view_id: viewId,
            duration_seconds: duration
        });
        
        navigator.sendBeacon('/track/view/end', new Blob([data], { type: 'application/json' }));
        
        // End article tracking
        if (isArticlePage && articleViewId) {
            const articleData = JSON.stringify({
                view_id: articleViewId,
                duration_seconds: duration
            });
            navigator.sendBeacon('/track/article/end', new Blob([articleData], { type: 'application/json' }));
        }
    }
    
    // Handle page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            endTracking();
        } else {
            startTime = Date.now();
            startTracking();
        }
    });
    
    // Handle page unload
    window.addEventListener('pagehide', function() {
        endTracking();
    });
    
    // Handle beforeunload as fallback
    window.addEventListener('beforeunload', function() {
        endTracking();
    });
    
    // Start tracking on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startTracking);
    } else {
        startTracking();
    }
})();

