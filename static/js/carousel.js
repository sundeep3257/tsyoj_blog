document.addEventListener('DOMContentLoaded', function() {
    const carousel = document.getElementById('articleCarousel');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const indicatorsContainer = document.getElementById('carouselIndicators');
    
    if (!carousel) return;
    
    const items = carousel.querySelectorAll('.carousel-item');
    const totalItems = items.length;
    let currentIndex = 0;
    
    // Determine items per view based on screen size
    function getItemsPerView() {
        return window.innerWidth > 768 ? 2 : 1;
    }
    
    let itemsPerView = getItemsPerView();
    
    // Update on resize
    window.addEventListener('resize', function() {
        const newItemsPerView = getItemsPerView();
        if (newItemsPerView !== itemsPerView) {
            itemsPerView = newItemsPerView;
            // Recalculate current index to stay in bounds
            const maxIndex = Math.max(0, totalItems - itemsPerView);
            if (currentIndex > maxIndex) {
                currentIndex = maxIndex;
            }
            updateCarousel();
        }
    });
    
    // Create indicators (one per item)
    if (indicatorsContainer && totalItems > 0) {
        for (let i = 0; i < totalItems; i++) {
            const indicator = document.createElement('div');
            indicator.className = 'indicator';
            if (i === 0) indicator.classList.add('active');
            indicator.addEventListener('click', () => goToSlide(i));
            indicatorsContainer.appendChild(indicator);
        }
    }
    
    function updateCarousel() {
        // Calculate card width percentage (accounting for gap)
        const cardWidthPercent = 100 / itemsPerView;
        const translateX = -currentIndex * cardWidthPercent;
        carousel.style.transform = `translateX(${translateX}%)`;
        
        // Update indicators
        if (indicatorsContainer) {
            const indicators = indicatorsContainer.querySelectorAll('.indicator');
            indicators.forEach((indicator, index) => {
                // Show active if the card is visible
                const isVisible = index >= currentIndex && index < currentIndex + itemsPerView;
                if (isVisible) {
                    indicator.classList.add('active');
                } else {
                    indicator.classList.remove('active');
                }
            });
        }
        
        // Update button states
        if (prevBtn) {
            prevBtn.style.opacity = currentIndex === 0 ? '0.5' : '1';
            prevBtn.style.cursor = currentIndex === 0 ? 'not-allowed' : 'pointer';
            prevBtn.disabled = currentIndex === 0;
        }
        if (nextBtn) {
            const maxIndex = Math.max(0, totalItems - itemsPerView);
            nextBtn.style.opacity = currentIndex >= maxIndex ? '0.5' : '1';
            nextBtn.style.cursor = currentIndex >= maxIndex ? 'not-allowed' : 'pointer';
            nextBtn.disabled = currentIndex >= maxIndex;
        }
    }
    
    function goToSlide(index) {
        if (index < 0) {
            currentIndex = 0;
        } else {
            const maxIndex = Math.max(0, totalItems - itemsPerView);
            currentIndex = Math.min(index, maxIndex);
        }
        updateCarousel();
    }
    
    function nextSlide() {
        const maxIndex = Math.max(0, totalItems - itemsPerView);
        if (currentIndex < maxIndex) {
            currentIndex++;
            updateCarousel();
        }
    }
    
    function prevSlide() {
        if (currentIndex > 0) {
            currentIndex--;
            updateCarousel();
        }
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', nextSlide);
    }
    
    if (prevBtn) {
        prevBtn.addEventListener('click', prevSlide);
    }
    
    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            prevSlide();
        } else if (e.key === 'ArrowRight') {
            nextSlide();
        }
    });
    
    // Touch/swipe support for mobile
    let touchStartX = 0;
    let touchEndX = 0;
    
    carousel.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    });
    
    carousel.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    });
    
    function handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                nextSlide();
            } else {
                prevSlide();
            }
        }
    }
    
    // Initialize
    updateCarousel();
});

