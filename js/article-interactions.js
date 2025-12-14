document.addEventListener('DOMContentLoaded', function() {
    const likeBtn = document.getElementById('likeBtn');
    
    if (likeBtn) {
        likeBtn.addEventListener('click', function() {
            const articleSlug = this.getAttribute('data-article-slug');
            const likeIcon = this.querySelector('.like-icon');
            const likeText = this.querySelector('.like-text');
            const likeCount = document.getElementById('likeCount');
            
            // Disable button during request
            this.disabled = true;
            
            fetch(`/article/${articleSlug}/like`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                // Update UI
                if (data.has_liked) {
                    this.classList.add('liked');
                    likeIcon.textContent = '♥';
                    likeText.textContent = 'Liked';
                } else {
                    this.classList.remove('liked');
                    likeIcon.textContent = '♡';
                    likeText.textContent = 'Like';
                }
                
                likeCount.textContent = data.like_count;
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            })
            .finally(() => {
                this.disabled = false;
            });
        });
    }
});

