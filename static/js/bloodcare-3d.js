import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const hero = document.querySelector(".welcome-section");
const canvas = hero?.querySelector(".bc-three-canvas");

if (hero && canvas && !canvas.dataset.initialized) {
    canvas.dataset.initialized = "true";

    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let renderer;

    try {
        renderer = new THREE.WebGLRenderer({
            canvas,
            alpha: true,
            antialias: true,
            powerPreference: "low-power"
        });
    } catch (error) {
        console.error("BloodCare 3D requires WebGL:", error);
    }

    if (renderer) {
        renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
        renderer.setClearColor(0x000000, 0);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.15;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        camera.position.set(1.4, 0, 11);

        scene.add(new THREE.AmbientLight(0xffb7c8, 1.5));

        const key = new THREE.PointLight(0xffd9e1, 100, 30);
        key.position.set(-3, 4, 6);
        scene.add(key);

        const red = new THREE.PointLight(0xff174f, 140, 28);
        red.position.set(4, 0, 3);
        scene.add(red);

        const rim = new THREE.PointLight(0xff718c, 90, 25);
        rim.position.set(1, 4, -3);
        scene.add(rim);

        // Parametric biconcave blood-disc geometry.
        function makeCellGeometry() {
            const positions = [];
            const indices = [];
            const segments = 48;
            const rings = 20;

            for (let side = 0; side < 2; side++) {
                const sign = side === 0 ? 1 : -1;
                const base = positions.length / 3;

                for (let rIndex = 0; rIndex <= rings; rIndex++) {
                    const r = rIndex / rings;

                    for (let j = 0; j <= segments; j++) {
                        const a = j / segments * Math.PI * 2;
                        const x = r * Math.cos(a);
                        const y = r * Math.sin(a);
                        const z = sign * (
                            0.04 + 0.18 * r * r -
                            0.16 * Math.exp(-Math.pow(r / 0.34, 2))
                        );
                        positions.push(x, y, z);
                    }
                }

                const row = segments + 1;

                for (let r = 0; r < rings; r++) {
                    for (let j = 0; j < segments; j++) {
                        const a = base + r * row + j;
                        const b = a + row;

                        if (side === 0) {
                            indices.push(a, b, a + 1, b, b + 1, a + 1);
                        } else {
                            indices.push(a, a + 1, b, b, a + 1, b + 1);
                        }
                    }
                }
            }

            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute(
                "position",
                new THREE.Float32BufferAttribute(positions, 3)
            );
            geometry.setIndex(indices);
            geometry.computeVertexNormals();
            return geometry;
        }

        const cellGeometry = makeCellGeometry();
        const cellMaterial = new THREE.MeshPhysicalMaterial({
            color: 0xe52b53,
            roughness: 0.3,
            metalness: 0.05,
            clearcoat: 0.9,
            clearcoatRoughness: 0.2,
            emissive: 0x4c0619,
            emissiveIntensity: 0.4,
            side: THREE.DoubleSide
        });

        const cells = [];
        const mobile = innerWidth < 600;
        const count = mobile ? 9 : 17;

        for (let i = 0; i < count; i++) {
            const mesh = new THREE.Mesh(cellGeometry, cellMaterial);
            const scale = 0.38 + Math.random() * 0.65;

            mesh.scale.set(scale, scale, scale);
            mesh.position.set(
                0.1 + Math.random() * 5.6,
                -2.1 + Math.random() * 4.4,
                -2 + Math.random() * 4
            );
            mesh.rotation.set(Math.random() * 3, Math.random() * 3, Math.random() * 3);
            scene.add(mesh);

            cells.push({
                mesh,
                x: mesh.position.x,
                y: mesh.position.y,
                phase: Math.random() * Math.PI * 2,
                speed: 0.25 + Math.random() * 0.5,
                spin: (Math.random() - 0.5) * 0.2
            });
        }

        const particleCount = mobile ? 220 : 550;
        const particlePositions = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
            particlePositions[i * 3] = -6 + Math.random() * 13;
            particlePositions[i * 3 + 1] = -3.5 + Math.random() * 7;
            particlePositions[i * 3 + 2] = -3 + Math.random() * 8;
        }

        const particleGeometry = new THREE.BufferGeometry();
        particleGeometry.setAttribute(
            "position",
            new THREE.BufferAttribute(particlePositions, 3)
        );

        const particleMaterial = new THREE.PointsMaterial({
            color: 0xffb0c0,
            size: 0.028,
            transparent: true,
            opacity: 0.7,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });

        const particles = new THREE.Points(particleGeometry, particleMaterial);
        scene.add(particles);

        const pointer = { x: 0, y: 0 };
        const target = { x: 0, y: 0 };
        let frame = 0;
        let visible = true;

        function resize() {
            const rect = hero.getBoundingClientRect();
            renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);
            camera.aspect = Math.max(1, rect.width) / Math.max(1, rect.height);
            camera.updateProjectionMatrix();
        }

        hero.addEventListener("pointermove", event => {
            const rect = hero.getBoundingClientRect();
            target.x = ((event.clientX - rect.left) / rect.width - 0.5) * 1.2;
            target.y = -((event.clientY - rect.top) / rect.height - 0.5) * 0.7;
        }, { passive: true });

        hero.addEventListener("pointerleave", () => {
            target.x = 0;
            target.y = 0;
        }, { passive: true });

        const resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(hero);

        const visibilityObserver = new IntersectionObserver(entries => {
            visible = entries[0].isIntersecting;
        });
        visibilityObserver.observe(hero);

        resize();

        function animate() {
            frame = requestAnimationFrame(animate);
            if (!visible || document.hidden) return;

            const t = performance.now() * 0.00035;
            pointer.x += (target.x - pointer.x) * 0.035;
            pointer.y += (target.y - pointer.y) * 0.035;

            camera.position.x = 1.4 + pointer.x * 0.5;
            camera.position.y = pointer.y * 0.4;
            camera.lookAt(1.5 + pointer.x * 0.15, pointer.y * 0.12, 0);

            if (!reducedMotion) {
                cells.forEach(item => {
                    item.mesh.position.x = item.x + Math.sin(t * item.speed + item.phase) * 0.24;
                    item.mesh.position.y = item.y + Math.sin(t * 1.3 + item.phase) * 0.17;
                    item.mesh.rotation.z += item.spin * 0.008;
                    item.mesh.rotation.x += item.spin * 0.003;
                });

                particles.rotation.y = Math.sin(t * 0.6) * 0.04;
            }

            renderer.render(scene, camera);
        }

        animate();

        window.addEventListener("pagehide", () => {
            cancelAnimationFrame(frame);
            resizeObserver.disconnect();
            visibilityObserver.disconnect();
            cellGeometry.dispose();
            cellMaterial.dispose();
            particleGeometry.dispose();
            particleMaterial.dispose();
            renderer.dispose();
        }, { once: true });
    }
}