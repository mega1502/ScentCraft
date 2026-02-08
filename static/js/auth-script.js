document.addEventListener('DOMContentLoaded', () => {
    const loginTab = document.getElementById('tab-login');
    const signupTab = document.getElementById('tab-signup');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');

    if (loginTab && signupTab && loginForm && signupForm) {
        
        loginTab.addEventListener('click', () => {
            // تنشيط تاب الدخول
            loginTab.classList.add('active');
            signupTab.classList.remove('active');
            
            // إظهار فورم الدخول وإخفاء التسجيل
            loginForm.classList.remove('hidden');
            signupForm.classList.add('hidden');
            
            // تعديل الرابط في المتصفح (شكليات)
            const url = new URL(window.location);
            url.searchParams.set('mode', 'login');
            window.history.pushState({}, '', url);
        });

        signupTab.addEventListener('click', () => {
            // تنشيط تاب التسجيل
            signupTab.classList.add('active');
            loginTab.classList.remove('active');
            
            // إظهار فورم التسجيل وإخفاء الدخول
            signupForm.classList.remove('hidden');
            loginForm.classList.add('hidden');
            
            // تعديل الرابط
            const url = new URL(window.location);
            url.searchParams.set('mode', 'signup');
            window.history.pushState({}, '', url);
        });

        // لو الرابط جاي فيه mode=signup نفتح التسجيل علطول
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mode') === 'signup') {
            signupTab.click();
        }
    }
});