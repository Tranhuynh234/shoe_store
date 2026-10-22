/* Giày Tuấn */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-toggle-password]').forEach(function (toggle) {
        toggle.addEventListener('change', function () {
            var field = document.querySelector(toggle.getAttribute('data-toggle-password'));
            if (field) field.type = toggle.checked ? 'text' : 'password';
        });
    });

    var openBtn = document.getElementById('openMenuBtn');
    var closeBtn = document.getElementById('closeMenuBtn');
    var sideMenu = document.getElementById('sideMenu');
    var overlay = document.getElementById('menuOverlay');

    function closeMenu() {
        if (sideMenu) sideMenu.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = 'auto';
    }

    if (sideMenu && overlay) {
        document.querySelectorAll('[data-open-menu], #openMenuBtn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                sideMenu.classList.add('active');
                overlay.classList.add('active');
                document.body.style.overflow = 'hidden'; 
            });
        });
        if (closeBtn) closeBtn.addEventListener('click', closeMenu);
        overlay.addEventListener('click', closeMenu);
        document.addEventListener('keydown', function (e) { 
            if (e.key === 'Escape') closeMenu(); 
        });
    }

    // Xác nhận trước thao tác quan trọng: <form data-confirm="...">
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!window.confirm(form.dataset.confirm)) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        });
    });

    // Trạng thái loading
    document.querySelectorAll('form[method="post"]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (e.defaultPrevented) return;
            var btn = e.submitter || form.querySelector('button[type="submit"]');
            if (!btn || btn.dataset.noLoading !== undefined) return;
            setTimeout(function () {
                form.querySelectorAll('button[type="submit"]').forEach(function (b) { b.disabled = true; });
                btn.classList.add('is-loading');
                if (btn.dataset.loadingText) btn.textContent = btn.dataset.loadingText;
            }, 0);
        });
    });

    // Đóng thông báo
    document.querySelectorAll('.flash .flash-close').forEach(function (b) {
        b.addEventListener('click', function () { b.closest('.flash').remove(); });
    });

    // Thư viện ảnh sản phẩm
    var mainImg = document.getElementById('galleryMain');
    document.querySelectorAll('[data-gallery-thumb]').forEach(function (t) {
        t.addEventListener('click', function () {
            if (mainImg) mainImg.src = t.dataset.src;
            document.querySelectorAll('[data-gallery-thumb]').forEach(function (x) { x.classList.remove('active'); });
            t.classList.add('active');
        });
    });

    // Thẻ sản phẩm: hover đổi ảnh + rê chuột vào ảnh nhỏ để xem từng ảnh
    document.querySelectorAll('[data-card]').forEach(function (card) {
        var main = card.querySelector('.card-main');
        if (!main) return;
        var thumbs = card.querySelectorAll('.card-thumb');
        var preloaded = false;

        function show(src) {
            if (src && main.getAttribute('src') !== src) main.src = src;
            thumbs.forEach(function (t) { t.classList.toggle('active', t.dataset.src === src); });
        }
        function preload() { // tải trước để lúc đổi ảnh không bị nháy
            if (preloaded) return;
            preloaded = true;
            thumbs.forEach(function (t) { new Image().src = t.dataset.src; });
        }
        function enter() { preload(); show(main.dataset.hover); }
        function leave() { show(main.dataset.default); }

        card.addEventListener('mouseenter', enter);
        card.addEventListener('mouseleave', leave);
        card.addEventListener('focusin', function () { if (card.matches(':focus-visible')) enter(); });
        card.addEventListener('focusout', function (e) { if (!card.contains(e.relatedTarget)) leave(); });
        thumbs.forEach(function (t) {
            t.addEventListener('mouseenter', function () { show(t.dataset.src); });
        });
    });

    // Giao diện sáng/tối
    var themeBtn = document.getElementById('themeToggle');

    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            var currentTheme = document.documentElement.getAttribute('data-theme');
            var next = currentTheme === 'dark' ? 'light' : 'dark';

            document.documentElement.setAttribute('data-theme', next);
            try {
                localStorage.setItem('theme', next);
            } catch (e) { }
        });
    }

    // Xử lý popup chọn ngôn ngữ
    const langWrapper = document.querySelector(".language-wrapper");
    const langPopup = document.getElementById("languagePopup");
    const langToggle = document.getElementById("languageToggle");

    if (langWrapper && langPopup) {
        langWrapper.addEventListener("click", function (event) {
            event.stopPropagation();
            // Nếu click vào các thành phần bên trong popup chọn ngôn ngữ (như radio, nút lưu), để yên cho form hoạt động
            if (event.target.closest('.language-popup') && !event.target.closest('#languageToggle')) {
                return;
            }
            langPopup.hidden = !langPopup.hidden;
            if (langToggle) {
                langToggle.setAttribute('aria-expanded', langPopup.hidden ? 'false' : 'true');
            }
        });

        document.addEventListener("click", function (event) {
            if (!event.target.closest(".language-wrapper")) {
                langPopup.hidden = true;
                if (langToggle) langToggle.setAttribute('aria-expanded', 'false');
            }
        });
    }
    // Bảng người dùng (Đăng ký / Đăng nhập / Sáng-tối / Ngôn ngữ)
    var userBtn = document.getElementById('userMenuToggle');
    var userPopup = document.getElementById('userPopup');

    if (userBtn && userPopup) {
        function setUserMenu(open) {
            userPopup.hidden = !open;
            userBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
        userBtn.addEventListener('click', function (event) {
            event.stopPropagation();
            setUserMenu(userPopup.hidden);
        });
        document.addEventListener('click', function (event) {
            if (!event.target.closest('.user-menu')) setUserMenu(false);
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') setUserMenu(false);
        });
    }
    var heroHeader = document.querySelector('.header.header-hero');

    if (heroHeader) {
        function syncHeader() {
            heroHeader.classList.toggle('is-scrolled', window.scrollY > 40);
        }
        syncHeader();
        window.addEventListener('scroll', syncHeader, { passive: true });
    }
});

// Bấm Sản phẩm nam / nữ / Phụ kiện để xổ ra hoặc thu lại.

(function () {
    document.querySelectorAll('[data-sub-toggle]').forEach(function (a) {
        a.addEventListener('click', function (e) {
            e.preventDefault();
            var li = a.parentElement;
            var willOpen = !li.classList.contains('open');

            document.querySelectorAll('.side-menu-list li.has-sub.open').forEach(function (o) {
                o.classList.remove('open');
                o.querySelector('[data-sub-toggle]').setAttribute('aria-expanded', 'false');
            });

            if (willOpen) {
                li.classList.add('open');
                a.setAttribute('aria-expanded', 'true');
            }
        });
    });
})();

/* Trang Portfolio */
(() => {
    const stage = document.querySelector('.story-stage');
    const pin = document.querySelector('.story-pin');
    const paper = document.querySelector('.sp-paper');
    const track = document.getElementById('scrollTrack');
    const win = document.querySelector('.sp-window');
    const panels = [...document.querySelectorAll('.sp-panel')];
    const spreads = panels.map(p => p.querySelector('.bk'));
    const layers = [...document.querySelectorAll('.sp-bg')];
    const progress = document.getElementById('chapterProgressBar');
    const counter = document.getElementById('currentChapter');
    const titleEl = document.getElementById('currentTitle');
    const dots = [...document.querySelectorAll('.sp-dots a')];
    if (!stage || !pin || !paper || !track || !win || !panels.length) return;

    const mobile = window.matchMedia('(max-width: 900px)');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

    let maxX = 0, activeIndex = -1, activeLayer = 0, ticking = false;

    /* ---------- Dò ảnh ---------- */
    const ROOT = stage.dataset.imgRoot || '/static/images/';
    const FOLDERS = ['port', 'portfolio'];
    const EXTS = ['jpg', 'png', 'jpeg', 'webp', 'JPG', 'PNG'];
    const found = new Map();
    function findImage(names) {
        const key = names.join('|');
        if (found.has(key)) return found.get(key);
        const urls = [];
        FOLDERS.forEach(f => names.forEach(n => EXTS.forEach(e => urls.push(`${ROOT}${f}/${n}.${e}`))));
        const p = new Promise(resolve => {
            let i = 0;
            (function next() {
                if (i >= urls.length) return resolve(null);
                const probe = new Image(), url = urls[i++];
                probe.onload = () => resolve(url);
                probe.onerror = next;
                probe.src = url;
            })();
        });
        found.set(key, p);
        return p;
    }
    // Ảnh trong các khung
    document.querySelectorAll('.bk-photo img[data-name]').forEach(img => {
        findImage([img.dataset.name]).then(url => {
            if (!url) return;
            img.src = url;
            img.parentNode.classList.add('ok');
        });
    });

    /* ---------- Dò video ---------- */
    function findVideo(names) {
        const urls = [];
        ['port', 'portfolio', 'video', 'videos', ''].forEach(f => names.forEach(n => ['mp4', 'MP4', 'webm'].forEach(e => urls.push(`${ROOT}${f ? f + '/' : ''}${n}.${e}`))));
        return new Promise(resolve => {
            let i = 0;
            (function next() {
                if (i >= urls.length) return resolve(null);
                const probe = document.createElement('video'), url = urls[i++];
                probe.preload = 'metadata'; probe.muted = true;
                probe.onloadedmetadata = () => resolve(url);
                probe.onerror = next;
                probe.src = url;
            })();
        });
    }

    /* ---------- Bìa Kinh Thành ---------- */
    const cover = document.getElementById('spCover');
    if (cover) {
        document.body.classList.add('sp-locked');
        window.scrollTo(0, 0);
        const enter = document.getElementById('spEnter');
        const video = document.getElementById('spVideo');
        const unroll = document.getElementById('spUnroll');
        const skip = document.getElementById('spSkip');
        let hasVideo = false, unrollOk = false, finished = false, guard = null;

        // file video bìa 
        if (video && cover.dataset.video) {
            findVideo(cover.dataset.video.split(',')).then(url => {
                if (!url) return;
                video.src = url;
                video.load();
                hasVideo = true;
                cover.classList.add('has-video');
            });
        }

        // video cuốn chiếu: kiểm tra đã tải được chưa
        if (unroll) {
            if (unroll.readyState >= 1) unrollOk = true;
            unroll.addEventListener('loadedmetadata', () => { unrollOk = true; });
            unroll.addEventListener('error', () => console.warn('Không tải được video cuốn chiếu:', unroll.currentSrc || unroll.src));
        }

        // Y như bản gốc của bạn (dùng cho BỎ QUA / lỗi)
        function finish() {
            if (finished) return;
            finished = true;
            clearTimeout(guard);
            if (video) video.pause();
            if (unroll) { unroll.pause(); unroll.classList.add('out'); }
            if (skip) skip.hidden = true;
            document.body.classList.add('sp-revealed');
            cover.classList.add('done');
            setTimeout(() => {
                cover.hidden = true;
                document.body.classList.remove('sp-locked');
            }, reduced.matches ? 0 : 1300);
        }

        // Chuyển cảnh: cuốn chiếu thật hiện dần, video mờ đi, rồi bìa mờ theo
        function crossfade() {
            if (finished) return;
            finished = true;
            clearTimeout(guard);
            if (skip) skip.hidden = true;
            document.body.classList.add('sp-revealed');
            unroll.classList.add('out');
            setTimeout(() => cover.classList.add('done'), 500);
            setTimeout(() => {
                cover.hidden = true;
                document.body.classList.remove('sp-locked');
            }, reduced.matches ? 0 : 1800);
        }

        // Video Kinh Thành hết -> video cuốn chiếu chạy
        function playUnroll() {
            if (finished) return;
            if (!unroll || !unrollOk || reduced.matches) return finish();
            clearTimeout(guard);
            unroll.addEventListener('ended', crossfade, { once: true });
            unroll.addEventListener('error', finish, { once: true });
            unroll.addEventListener('timeupdate', function onT() {
                if (unroll.duration && unroll.duration - unroll.currentTime < 0.8) {
                    unroll.removeEventListener('timeupdate', onT);
                    crossfade();
                }
            });
            guard = setTimeout(() => { if (unroll.currentTime < 0.1) finish(); }, 6000);
            unroll.currentTime = 0;
            unroll.classList.add('show');
            const p = unroll.play();
            if (p && p.catch) p.catch(finish);
        }

        enter.addEventListener('mouseenter', () => { if (!hasVideo && !cover.classList.contains('opening')) cover.classList.add('peek'); });
        enter.addEventListener('mouseleave', () => cover.classList.remove('peek'));
        enter.addEventListener('click', () => {
            if (cover.classList.contains('opening') || cover.classList.contains('playing')) return;
            cover.classList.remove('peek');

             if (hasVideo) {
                document.body.classList.add('sp-match');   
                cover.classList.add('playing');
                // Bấm xong mới phát video
                cover.classList.add('playing');
                if (skip) skip.hidden = false;
                video.addEventListener('ended', playUnroll, { once: true });   
                video.addEventListener('error', finish, { once: true });
                const p = video.play();
                if (p && p.catch) p.catch(() => { video.muted = true; video.play().catch(finish); });
                guard = setTimeout(() => { if (video.currentTime < 0.1) finish(); }, 8000);
                return;
            }

            // Không có video: giữ hiệu ứng hai cánh cửa mở như cũ
            cover.classList.add('opening');
            document.body.classList.add('sp-revealed');
            setTimeout(() => {
                cover.hidden = true;
                document.body.classList.remove('sp-locked');
            }, reduced.matches ? 0 : 1900);
        });
        if (skip) skip.addEventListener('click', finish);
    }

    /* ---------- Ảnh chiếu chỉ ---------- */
    if (paper.dataset.names) {
        findImage(paper.dataset.names.split(',')).then(url => {
            if (!url) return;
            const im = new Image();
            im.onload = () => {
                const W = im.naturalWidth, H = im.naturalHeight;
                let bx = 0, by = 0, bw = W, bh = H;
                try {
                    const sc = Math.min(1, 700 / W), cw = Math.max(1, Math.round(W * sc)), ch = Math.max(1, Math.round(H * sc));
                    const cv = document.createElement('canvas'); cv.width = cw; cv.height = ch;
                    const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(im, 0, 0, cw, ch);
                    const d = cx.getImageData(0, 0, cw, ch).data;
                    let x0 = cw, y0 = ch, x1 = -1, y1 = -1;
                    for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) {
                        if (d[(y * cw + x) * 4 + 3] > 60) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
                    }
                    if (x1 > x0 && y1 > y0) { bx = x0 / sc; by = y0 / sc; bw = (x1 - x0 + 1) / sc; bh = (y1 - y0 + 1) / sc; }
                } catch (e) { /* không đọc được điểm ảnh: dùng cả ảnh */ }
                paper.style.setProperty('--sp-ratio', (bw / bh).toFixed(4));
                paper.style.setProperty('--sp-img-size', `${(W / bw * 100).toFixed(3)}% ${(H / bh * 100).toFixed(3)}%`);
                paper.style.setProperty('--sp-img-pos', `${W > bw ? (bx / (W - bw) * 100).toFixed(3) : 0}% ${H > bh ? (by / (H - bh) * 100).toFixed(3) : 0}%`);
                paper.style.setProperty('--sp-scroll-img', `url("${url}")`);
                paper.classList.add('has-img');
                setup();
            };
            im.src = url;
        });
    }
    if (cover && cover.dataset.names) {
        findImage(cover.dataset.names.split(',')).then(url => {
            if (url) cover.style.setProperty('--sp-cover', `url("${url}")`);
        });
    }

    /* ---------- Nền video theo mục ----------
       Mỗi mục lấy video theo data-bg (vd: bg-about -> images/port/bg-about.mp4 hoặc .webm).
       Chưa có video / video lỗi thì giữ ảnh nền cũ. Video tắt tiếng, tự lặp, chỉ phát video của mục đang xem. */
    const bgStage = document.getElementById('storyBackground');
    const bgShade = bgStage && bgStage.querySelector('.sp-bg-shade');
    const bgVids = new Map();
    function playBg(i) {
        const r = bgVids.get(i);
        if (!r || !r.el || reduced.matches) return;
        const pr = r.el.play();
        if (pr && pr.catch) pr.catch(() => {});
    }
    function bgVideo(i) {
        if (bgVids.has(i)) return bgVids.get(i);
        const rec = { el: null };
        bgVids.set(i, rec);
        const panel = panels[i];
        if (!bgStage || !panel || !panel.dataset.bg || reduced.matches) return rec;
        findVideo([panel.dataset.bg]).then(url => {
            if (!url) return;
            const v = document.createElement('video');
            v.className = 'sp-bgv';
            v.muted = true; v.loop = true; v.playsInline = true;
            v.setAttribute('muted', ''); v.setAttribute('playsinline', ''); v.setAttribute('aria-hidden', 'true');
            v.preload = 'auto';
            v.addEventListener('loadeddata', () => {
                v.classList.add('ready');
                if (activeIndex === i) playBg(i);
            });
            v.src = url;
            if (activeIndex === i) v.classList.add('on');
            bgStage.insertBefore(v, bgShade);
            rec.el = v;
        });
        return rec;
    }
    function syncBgVideos(index) {
        bgVideo(index);
        bgVideo(index + 1);                       // tải trước mục kế tiếp cho khỏi giật
        bgVids.forEach((r, i) => {
            if (!r.el) return;
            r.el.classList.toggle('on', i === index);
            if (i === index) playBg(i);
            else setTimeout(() => { if (activeIndex !== i) r.el.pause(); }, 900);
        });
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) playBg(activeIndex); });
    document.addEventListener('click', () => playBg(activeIndex), { once: true });   // một số trình duyệt chỉ cho phát sau lần chạm đầu

    /* ---------- Đổi nền theo mục ---------- */
    function setBackground(index) {
        if (index === activeIndex) return;
        activeIndex = index;
        const panel = panels[index];
        const next = layers[1 - activeLayer];
        next.style.backgroundImage = 'none';
        if (panel.dataset.bg) {
            findImage([panel.dataset.bg]).then(url => {
                if (url && activeIndex === index) next.style.backgroundImage = `url("${url}")`;
            });
        }
        next.classList.add('on');
        layers[activeLayer].classList.remove('on');
        activeLayer = 1 - activeLayer;

        syncBgVideos(index);

        counter.textContent = `${String(index + 1).padStart(2, '0')} / ${String(panels.length).padStart(2, '0')}`;
        titleEl.textContent = panel.dataset.title || '';
        dots.forEach((dot, i) => {
            if (i === index) dot.setAttribute('aria-current', 'location'); else dot.removeAttribute('aria-current');
        });
    }

    function setup() {
        if (mobile.matches) {
            stage.style.height = 'auto';
            track.style.transform = 'none';
            spreads.forEach(s => { if (s) { s.style.transform = ''; s.style.opacity = ''; } });
            stage.style.removeProperty('--sp-panel-w');
            maxX = 0;
            return;
        }
        stage.style.setProperty('--sp-panel-w', `${win.clientWidth}px`);
        maxX = Math.max(0, track.scrollWidth - win.clientWidth);
        stage.style.height = `${maxX + pin.offsetHeight}px`;
        update();
    }

    function update() {
        ticking = false;
        if (mobile.matches) return;
        const travelled = Math.min(maxX, Math.max(0, -stage.getBoundingClientRect().top));
        track.style.transform = `translate3d(${-travelled}px, 0, 0)`;
        const ratio = maxX > 0 ? travelled / maxX : 0;
        progress.style.width = `${ratio * 100}%`;
        setBackground(Math.min(panels.length - 1, Math.round(ratio * (panels.length - 1))));
    }

    function requestUpdate() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(update);
    }

    dots.forEach((dot, index) => {
        dot.addEventListener('click', event => {
            event.preventDefault();
            if (mobile.matches) { panels[index].scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth' }); return; }
            const stageTop = window.scrollY + stage.getBoundingClientRect().top;
            const targetX = maxX * index / Math.max(1, panels.length - 1);
            window.scrollTo({ top: stageTop + targetX, behavior: reduced.matches ? 'auto' : 'smooth' });
        });
    });

    // Điện thoại
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver(entries => {
            if (!mobile.matches) return;
            entries.forEach(e => { if (e.isIntersecting) setBackground(panels.indexOf(e.target)); });
        }, { rootMargin: '-45% 0px -45% 0px' });
        panels.forEach(p => io.observe(p));
    }

    /* ---------- Xem ảnh lớn ---------- */
    const box = document.getElementById('spLightbox');
    if (box) {
        const big = document.getElementById('spBig');
        const cap = document.getElementById('spCap');
        document.querySelectorAll('.sp-open').forEach(btn => {
            btn.addEventListener('click', () => {
                big.src = btn.dataset.src;
                big.alt = btn.dataset.cap;
                cap.textContent = btn.dataset.cap;
                if (box.showModal) box.showModal(); else box.setAttribute('open', '');
            });
        });
        const close = () => { if (box.close) box.close(); else box.removeAttribute('open'); };
        document.getElementById('spClose').addEventListener('click', close);
        box.addEventListener('click', e => { if (e.target === box) close(); });
    }

    /* ---------- Tự căn giữa ---------- */
    let snapTimer = null;
    function snapToPanel() {
        if (mobile.matches || maxX <= 0 || panels.length < 2) return;
        const stageTop = window.scrollY + stage.getBoundingClientRect().top;
        const travelled = window.scrollY - stageTop;
        if (travelled < 0 || travelled > maxX) return;           
        const step = maxX / (panels.length - 1);
        const target = stageTop + Math.round(travelled / step) * step;
        if (Math.abs(target - window.scrollY) > 2) {
            window.scrollTo({ top: target, behavior: reduced.matches ? 'auto' : 'smooth' });
        }
    }
    window.addEventListener('scroll', () => {
        clearTimeout(snapTimer);
        snapTimer = setTimeout(snapToPanel, 160);
    }, { passive: true });

    window.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', setup);
    window.addEventListener('load', setup);
    mobile.addEventListener && mobile.addEventListener('change', setup);

    setBackground(0);
    setup();
})();