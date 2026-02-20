const mobileMenu = document.getElementById('mobile-menu');
const navLinks = document.querySelector('.right-section');

mobileMenu.addEventListener('click', () => {
    navLinks.classList.toggle('active');
});
