document.addEventListener("DOMContentLoaded", function() {

    // --- 1. كود موحد لكل الصفحات ---
    const siteHeader = document.getElementById("site-header");
    const menuButton = document.getElementById("mobile-menu-btn");

    // الكود هيشتغل لو لقى الهيدر والزرار
    if (siteHeader && menuButton) {
        
        // --- أ) تأثير الـ Scroll (لكل الصفحات) ---
        function handleScroll() {
            if (window.scrollY > 50) {
                siteHeader.classList.add("scrolled");
            } else {
                siteHeader.classList.remove("scrolled");
            }
        }
        // تطبيق تأثير السكرول على كل الصفحات
        window.addEventListener("scroll", handleScroll);
        // استدعاء الدالة أول مرة عشان لو الصفحة فتحت وهي أصلاً عاملة سكرول
        handleScroll(); 


        // --- ب) فتح وإغلاق قائمة الموبايل (لكل الصفحات) ---
        const mainNav = document.getElementById("main-nav");
        const headerActions = document.querySelector(".header-actions");
        const headerContainer = siteHeader.querySelector(".container"); 

        function toggleMenu() {
            mainNav.classList.toggle("active");
            headerActions.classList.toggle("active"); 
            
            if (mainNav.classList.contains("active")) {
                // لو القائمة فتحت، انقل الأزرار جواها
                mainNav.appendChild(headerActions);
            } else {
                // لو القائمة قفلت، رجع الأزرار مكانها (قبل زرار الموبايل)
                headerContainer.insertBefore(headerActions, menuButton);
            }
        }
        menuButton.addEventListener("click", toggleMenu);
    } // نهاية الكود الموحد

    // --- (تم حذف كود المتجر المنفصل) ---

});

