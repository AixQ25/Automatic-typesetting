;;; ============================================================
;;;  NEST v20260801-pair  -  AutoCAD 2007 / Win7 32bit
;;;  ONLY load:  (load "D:/NEST.LSP")
;;;  then type:  NEST
;;;  Verify load message: [NEST] loaded. Command: NEST
;;;  v20260801-pair: 新增"配对嵌合"(复杂件旋转180嵌合成超单元再排)
;;; ============================================================

(vl-load-com)

;;; ---------- ?????? ----------
(setq *NEST-BOARD-W*     600.0)
(setq *NEST-BOARD-H*     850.0)
(setq *NEST-SPACING*      10.0)
(setq *NEST-MARGIN*       10.0)
(setq *NEST-LAYER*        "NEST-OUT")
(setq *NEST-LAYER-COLOR*  1)
(setq *NEST-OFFSET-X*     50.0)
(setq *NEST-OFFSET-Y*      0.0)
(setq *NEST-BOARD-GAP*    50.0)
(setq *NEST-MAX-ROW-W*  6000.0)
(setq *NEST-ROW-GAP*      50.0)
(setq *NEST-EPS*           1.0e-4)
(setq *NEST-CONTAIN-TOL*   2.0)
(setq *NEST-CLUSTER-GAP*   5.0)
(setq *NEST-MIN-AREA*      0.5)
(setq *NEST-HALF-PI*       (atan 1.0 0.0))
;; --- 配对嵌合参数 ---
(setq *NEST-PAIR-ENABLED*    T)   ; 是否启用配对嵌合
(setq *NEST-PAIR-WIN*        8.0) ; 配对收益阈值(百分比)，低于此不成对
(setq *NEST-PAIR-SAMPLES*    40)  ; 外轮廓采样/抽稀点数（越多间距判定越准，越慢）
(setq *NEST-PAIR-FILL-MAX*   0.85); 仅对 bbox 填充率低于此值的复杂件配对
(setq *NEST-PAIR-MAX-CAND*   200) ; 配对候选上限（超出按面积取前 N，防卡死）
(setq *NEST-PAIR-MAX-TRY*    400) ; 每次 NEST 最多尝试的配对对数上限


;;; ---------- ?????? ----------
(defun C:NEST ( / *error* ss ents units bbox base-x base-y placements nboards oldcmd pairres)
  (defun *error* (msg)
    (if oldcmd (setvar "CMDECHO" oldcmd))
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\n[NEST ERROR] " msg)))
    (princ))
  (setq oldcmd (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)
  (princ "\n===== NEST START =====")
  (princ "\nSelect objects: ")
  (setq ss (ssget))
  (if (not ss)
    (princ "\n[NEST] nothing selected.")
    (progn
      (princ (strcat "\n[NEST] selected " (itoa (sslength ss))))
      (setq ents (nest-get-entities ss))
      (princ (strcat "\n[NEST] extracted " (itoa (length ents))))
      (if (< (length ents) 1)
        (princ "\n[NEST] no valid geometry.")
        (progn
          (setq units (nest-build-units ents))
          (princ (strcat "\n[NEST] units = " (itoa (length units))))
          (if (and *NEST-PAIR-ENABLED* (> (length units) 1))
            (progn
              (setq pairres (nest-pair-units units *NEST-SPACING* *NEST-PAIR-WIN*))
              (setq units (car pairres))
              (princ (strcat "\n[NEST] paired " (itoa (cadr pairres))
                             " superunits, units = " (itoa (length units))))))
          (if (< (length units) 1)
            (princ "\n[NEST] no packable units.")
            (progn
              (setq bbox (nest-units-bbox units))
              (setq base-x (+ (nth 2 bbox) *NEST-OFFSET-X*))
              (setq base-y (+ (nth 3 bbox) *NEST-OFFSET-Y*))
              (nest-ensure-layer *NEST-LAYER* *NEST-LAYER-COLOR*)
              (princ "\n[NEST] packing...")
              (setq placements
                    (nest-pack units *NEST-BOARD-W* *NEST-BOARD-H*
                               *NEST-SPACING* *NEST-MARGIN*))
              (princ (strcat "\n[NEST] placed " (itoa (length placements))))
              (setq nboards
                    (nest-draw placements base-x base-y
                               *NEST-BOARD-W* *NEST-BOARD-H*))
              (princ (strcat "\n[NEST] DONE: "
                             (itoa (length placements)) " parts -> "
                             (itoa nboards) " boards"))
              (command "._REGEN")))))))
  (setvar "CMDECHO" oldcmd)
  (princ "\n===== NEST END =====")
  (princ))


;;; ---------- ?????VLA bbox?????? ename ----------
(defun C:NS () (C:NEST))


(defun nest-get-entities (ss / i n out rec)
  (setq i 0 n (sslength ss) out '())
  (while (< i n)
    (setq rec (nest-extract (ssname ss i) i))
    (if rec (setq out (cons rec out)))
    (setq i (1+ i)))
  (reverse out))

(defun nest-extract (e idx / res)
  (setq res (vl-catch-all-apply 'nest-extract-safe (list e idx)))
  (if (vl-catch-all-error-p res) nil res))

(defun nest-extract-safe (e idx / typ layer obj mn mx xmin ymin xmax ymax w h)
  (setq typ (cdr (assoc 0 (entget e))))
  (setq layer (cdr (assoc 8 (entget e))))
  (if (member typ '("TEXT" "MTEXT" "DIMENSION" "LEADER" "TOLERANCE"
                    "VIEWPORT" "ATTRIB" "ATTDEF" "SEQEND" "VERTEX"
                    "3DSOLID" "BODY" "REGION" "WIPEOUT"))
    nil
    (progn
      (setq obj (vlax-ename->vla-object e))
      (vla-getboundingbox obj 'mn 'mx)
      (setq mn (vlax-safearray->list mn)
            mx (vlax-safearray->list mx)
            xmin (car mn) ymin (cadr mn)
            xmax (car mx) ymax (cadr mx)
            w (- xmax xmin)
            h (- ymax ymin))
      (if (or (< w *NEST-EPS*) (< h *NEST-EPS*) (< (* w h) *NEST-MIN-AREA*))
        nil
        (list (cons 'ename e)
              (cons 'layer layer)
              (cons 'typ typ)
              (cons 'w w)
              (cons 'h h)
              (cons 'ox xmin)
              (cons 'oy ymin)
              (cons 'idx idx))))))


;;; ---------- ???? ----------
(defun nest-rec-bbox (rec)
  (list (cdr (assoc 'ox rec))
        (cdr (assoc 'oy rec))
        (+ (cdr (assoc 'ox rec)) (cdr (assoc 'w rec)))
        (+ (cdr (assoc 'oy rec)) (cdr (assoc 'h rec)))))

(defun nest-bbox-union (a b)
  (list (min (nth 0 a) (nth 0 b))
        (min (nth 1 a) (nth 1 b))
        (max (nth 2 a) (nth 2 b))
        (max (nth 3 a) (nth 3 b))))

(defun nest-bbox-contains (ou in / tol)
  (setq tol *NEST-CONTAIN-TOL*)
  (and (<= (- (nth 0 ou) (nth 0 in)) tol)
       (<= (- (nth 1 ou) (nth 1 in)) tol)
       (<= (- (nth 2 in) (nth 2 ou)) tol)
       (<= (- (nth 3 in) (nth 3 ou)) tol)))

(defun nest-bbox-center-in (ou in / cx cy)
  (setq cx (* 0.5 (+ (nth 0 in) (nth 2 in)))
        cy (* 0.5 (+ (nth 1 in) (nth 3 in))))
  (and (>= cx (- (nth 0 ou) *NEST-CONTAIN-TOL*))
       (<= cx (+ (nth 2 ou) *NEST-CONTAIN-TOL*))
       (>= cy (- (nth 1 ou) *NEST-CONTAIN-TOL*))
       (<= cy (+ (nth 3 ou) *NEST-CONTAIN-TOL*))))

(defun nest-units-bbox (units / all u bb)
  (setq all nil)
  (foreach u units
    (setq bb (list (cdr (assoc 'ox u))
                   (cdr (assoc 'oy u))
                   (+ (cdr (assoc 'ox u)) (cdr (assoc 'w u)))
                   (+ (cdr (assoc 'oy u)) (cdr (assoc 'h u)))))
    (setq all (if all (nest-bbox-union all bb) bb)))
  (if all all '(0.0 0.0 0.0 0.0)))


;;; ---------- ??????????? + ??? ????? ----------
(defun nest-should-merge (b1 b2 / gap)
  (setq gap *NEST-CLUSTER-GAP*)
  (or (nest-bbox-contains b1 b2)
      (nest-bbox-contains b2 b1)
      (nest-bbox-center-in b1 b2)
      (nest-bbox-center-in b2 b1)
      (and (<= (nth 0 b1) (+ (nth 2 b2) gap))
           (<= (nth 0 b2) (+ (nth 2 b1) gap))
           (<= (nth 1 b1) (+ (nth 3 b2) gap))
           (<= (nth 1 b2) (+ (nth 3 b1) gap)))))

(defun nest-uf-find (uf i / p)
  (setq p (cdr (assoc i uf)))
  (while (and p (not (eq p i)) (/= p i))
    (setq i p)
    (setq p (cdr (assoc i uf))))
  i)

(defun nest-uf-union (uf a b / ra rb pair)
  (setq ra (nest-uf-find uf a)
        rb (nest-uf-find uf b))
  (if (or (null ra) (null rb) (= ra rb))
    uf
    (progn
      (setq pair (assoc ra uf))
      (if pair (subst (cons ra rb) pair uf) uf))))

(defun nest-build-units (ents /
                         max-w max-h filtered rec rw rh
                         n i j bboxes uf ri groups g pair
                         members ub bb enames units nw nh)
  (setq max-w (- *NEST-BOARD-W* (* 2.0 *NEST-MARGIN*))
        max-h (- *NEST-BOARD-H* (* 2.0 *NEST-MARGIN*))
        filtered '())
  (foreach rec ents
    (setq rw (cdr (assoc 'w rec))
          rh (cdr (assoc 'h rec)))
    (if (and (<= rw max-w) (<= rh max-h))
      (setq filtered (cons rec filtered))))
  (setq filtered (reverse filtered))
  (if (not filtered)
    (progn (princ "\n[NEST] all oversized, skip.") '())
    (progn
      (setq n (length filtered)
            bboxes '()
            uf '()
            i 0)
      (princ (strcat "\n[NEST] cluster input " (itoa n)))
      (while (< i n)
        (setq bboxes (cons (nest-rec-bbox (nth i filtered)) bboxes))
        (setq uf (cons (cons i i) uf))
        (setq i (1+ i)))
      (setq bboxes (reverse bboxes)
            uf (reverse uf))
      ;; union-find
      (setq i 0)
      (while (< i n)
        (setq j (1+ i))
        (while (< j n)
          (if (nest-should-merge (nth i bboxes) (nth j bboxes))
            (setq uf (nest-uf-union uf i j)))
          (setq j (1+ j)))
        (setq i (1+ i)))
      ;; group by root
      (setq groups '())
      (setq i 0)
      (while (< i n)
        (setq ri (nest-uf-find uf i)
              pair (assoc ri groups))
        (if pair
          (setq groups (subst (cons ri (cons i (cdr pair))) pair groups))
          (setq groups (cons (cons ri (list i)) groups)))
        (setq i (1+ i)))
      ;; make units
      (setq units '())
      (foreach g groups
        (setq members (cdr g)
              ub nil
              enames '())
        (foreach i members
          (setq bb (nth i bboxes)
                rec (nth i filtered)
                enames (cons (cdr (assoc 'ename rec)) enames)
                ub (if ub (nest-bbox-union ub bb) bb)))
        (setq nw (- (nth 2 ub) (nth 0 ub))
              nh (- (nth 3 ub) (nth 1 ub))
              units
              (cons (list (cons 'enames (reverse enames))
                          (cons 'w nw)
                          (cons 'h nh)
                          (cons 'ox (nth 0 ub))
                          (cons 'oy (nth 1 ub))
                          (cons 'n (length members)))
                    units))
        (princ (strcat "\n  unit " (itoa (length units)) ": "
                       (rtos nw 2 1) "x" (rtos nh 2 1)
                       " (" (itoa (length members)) " ents)")))
      (reverse units))))


;;; ---------- ???? ----------
(defun nest-pack (units bw bh sp mg /
                  sorted remaining boards safe bidx res placed rem1)
  (setq sorted (nest-sort-area units)
        remaining sorted
        boards '()
        safe 0
        bidx 0)
  (while (and remaining (< safe 500))
    (setq safe (1+ safe)
          res (nest-pack-board remaining bw bh sp mg)
          placed (car res)
          rem1 (cdr res))
    (if (not placed)
      (progn (princ "\n[NEST] warn: some parts too big")
             (setq remaining nil))
      (progn
        (foreach p placed
          (setq boards (cons (append p (list bidx)) boards)))
        (setq remaining rem1
              bidx (1+ bidx)))))
  (reverse boards))

(defun nest-pack-board (remaining bw bh sp mg /
                        minx miny maxx maxy out newrem rec w h best rot is-super)
  (setq minx mg miny mg
        maxx (- bw mg) maxy (- bh mg)
        out '() newrem '())
  (foreach rec remaining
    (setq w (cdr (assoc 'w rec))
          h (cdr (assoc 'h rec))
          is-super (cdr (assoc 'parts rec))
          best (nest-place-best w h minx miny maxx maxy sp out is-super))
    (if best
      (progn
        (setq rot (car best))
        (setq out (cons (list rec (nth 1 best) (nth 2 best) rot) out)))
      (setq newrem (cons rec newrem))))
  (cons (reverse out) (reverse newrem)))

(defun nest-sort-area (units / pairs)
  (setq pairs
        (mapcar
          '(lambda (r)
             (list (* (cdr (assoc 'w r)) (cdr (assoc 'h r))) r))
          units))
  (mapcar 'cadr
          (vl-sort pairs '(lambda (a b) (> (car a) (car b))))))

(defun nest-place-best (w h minx miny maxx maxy sp placed is-super /
                        p0 rot0 p90 rot90)
  ;; Try both 0/90, pick whichever slides lower (row-first).
  ;; When same position: prefer smaller actual width (fits more per row).
  ;; is-super 时（超单元）不尝试旋转，保持配对确定的朝向。
  (setq p0  (nest-find-pos w h minx miny maxx maxy sp placed) rot0 nil)
  (setq p90 (nest-find-pos h w minx miny maxx maxy sp placed) rot90 T)
  (if is-super
    (if p0 (list rot0 (car p0) (cadr p0)) nil)
    (cond
      ((and p0 p90)
        (cond
          ((< (cadr p90) (cadr p0))
            (list rot90 (car p90) (cadr p90)))
          ((and (equal (cadr p90) (cadr p0) *NEST-EPS*)
                (< (car p90) (car p0)))
            (list rot90 (car p90) (cadr p90)))
          ((and (equal (cadr p90) (cadr p0) *NEST-EPS*)
                (equal (car p90) (car p0) *NEST-EPS*)
                (< h w))
            (list rot90 (car p90) (cadr p90)))
          (t
            (list rot0  (car p0)  (cadr p0)))))
      (p0  (list rot0  (car p0)  (cadr p0)))
      (p90 (list rot90 (car p90) (cadr p90)))
      (t nil))))

(defun nest-find-pos (w h minx miny maxx maxy sp placed /
                      cands px py pw ph top right c found)
  (setq cands (list (list minx miny)))
  (foreach pp placed
    (setq px (nth 1 pp) py (nth 2 pp)
          pw (+ (nest-pl-w pp) sp)
          ph (+ (nest-pl-h pp) sp)
          top (+ py ph)
          right (+ px pw))
    (if (<= (+ top h) maxy)
      (setq cands (cons (list px top) cands)))
    (if (<= (+ right w) maxx)
      (setq cands (cons (list right py) cands)))
    (if (and (<= (+ right w) maxx) (<= (+ top h) maxy))
      (setq cands (cons (list right top) cands)))
    (if (>= (- px w) minx)
      (progn
        (setq cands (cons (list (- px w) py) cands))
        (if (<= (+ top h) maxy)
          (setq cands (cons (list (- px w) top) cands))))))
  (setq cands (nest-uniq cands))
  ;; row-first: smaller y first, then smaller x
  (setq cands
        (vl-sort cands
                 '(lambda (a b)
                    (or (< (cadr a) (cadr b))
                        (and (equal (cadr a) (cadr b) *NEST-EPS*)
                             (< (car a) (car b)))))))
  (setq found nil)
  (while (and cands (not found))
    (setq c (car cands) cands (cdr cands))
    (if (nest-can-place (car c) (cadr c) w h minx miny maxx maxy sp placed)
      (setq found
            (nest-slide (car c) (cadr c) w h minx miny maxx maxy sp placed))))
  found)

(defun nest-pl-w (p)
  (if (nth 3 p)
    (cdr (assoc 'h (car p)))
    (cdr (assoc 'w (car p)))))

(defun nest-pl-h (p)
  (if (nth 3 p)
    (cdr (assoc 'w (car p)))
    (cdr (assoc 'h (car p)))))

(defun nest-can-place (x y w h minx miny maxx maxy sp placed /
                       px py pw ph ok)
  (if (or (< x minx) (< y miny)
          (> (+ x w) maxx) (> (+ y h) maxy))
    nil
    (progn
      (setq ok T)
      (foreach pp placed
        (setq px (nth 1 pp) py (nth 2 pp)
              pw (nest-pl-w pp) ph (nest-pl-h pp))
        (if (and (< x (+ px pw sp))
                 (> (+ x w sp) px)
                 (< y (+ py ph sp))
                 (> (+ y h sp) py))
          (setq ok nil)))
      ok)))

(defun nest-slide (x y w h minx miny maxx maxy sp placed / step)
  (setq step 1.0)
  (while (and (>= (- y step) miny)
              (nest-can-place x (- y step) w h minx miny maxx maxy sp placed))
    (setq y (- y step)))
  (while (and (>= (- x step) minx)
              (nest-can-place (- x step) y w h minx miny maxx maxy sp placed))
    (setq x (- x step)))
  (while (and (>= (- y step) miny)
              (nest-can-place x (- y step) w h minx miny maxx maxy sp placed))
    (setq y (- y step)))
  (list x y))

(defun nest-uniq (lst / out)
  (setq out '())
  (foreach x lst
    (if (not (member x out))
      (setq out (cons x out))))
  (reverse out))


;;; ---------- ???? + ??????? ----------
(defun nest-draw (placements bx by bw bh /
                  cur-x cur-y row-max cur-board bid)
  (if (not placements)
    0
    (progn
      (setq cur-x bx cur-y by row-max 0.0 cur-board -1)
      (foreach p placements
        (setq bid (nth 4 p))
        (if (/= bid cur-board)
          (progn
            (if (> cur-board -1)
              (progn
                (setq cur-x (+ cur-x bw *NEST-BOARD-GAP*))
                (if (> (+ cur-x bw) (+ bx *NEST-MAX-ROW-W*))
                  (progn
                    (setq cur-x bx)
                    (setq cur-y (+ cur-y row-max *NEST-ROW-GAP*))
                    (setq row-max 0.0)))))
            (nest-draw-board cur-x cur-y bw bh)
            (setq cur-board bid
                  row-max (max row-max bh))))
        (nest-move-unit (nth 0 p) (list cur-x cur-y)
                        (nth 1 p) (nth 2 p) (nth 3 p)))
      (1+ cur-board))))

(defun nest-draw-board (x y w h)
  (entmake (list (cons 0 "LWPOLYLINE")
                 (cons 100 "AcDbEntity")
                 (cons 8 *NEST-LAYER*)
                 (cons 100 "AcDbPolyline")
                 (cons 90 4)
                 (cons 70 1)
                 (cons 10 (list x y 0.0))
                 (cons 10 (list (+ x w) y 0.0))
                 (cons 10 (list (+ x w) (+ y h) 0.0))
                 (cons 10 (list x (+ y h) 0.0)))))

(defun nest-move-unit (unit base bx-on by-on rot / parts)
  (setq parts (cdr (assoc 'parts unit)))
  (if parts
    (nest-move-superunit unit base bx-on by-on rot)
    (nest-move-unit-bbox unit base bx-on by-on rot)))

(defun nest-move-unit-bbox (unit base bx-on by-on rot /
                       uox uoy uh enames e obj origin dest dx dy res)
  (setq uox (cdr (assoc 'ox unit))
        uoy (cdr (assoc 'oy unit))
        uh  (cdr (assoc 'h unit))
        enames (cdr (assoc 'enames unit))
        origin (vlax-3d-point (list uox uoy 0.0))
        dx (+ (car base) bx-on (if rot uh 0.0))
        dy (+ (cadr base) by-on)
        dest (vlax-3d-point (list dx dy 0.0)))
  (foreach e enames
    (setq res
          (vl-catch-all-apply
            'nest-move-one
            (list e origin dest rot)))
    (if (vl-catch-all-error-p res)
      (princ (strcat "\n[NEST] move fail: "
                     (vl-catch-all-error-message res))))))

(defun nest-move-one (e origin dest rot / obj)
  (if (and e (entget e))
    (progn
      (setq obj (vlax-ename->vla-object e))
      (if rot (vla-rotate obj origin *NEST-HALF-PI*))
      (vla-move obj origin dest))))


;;; ---------- ??? ----------
(defun nest-ensure-layer (name color)
  (if (not (tblsearch "LAYER" name))
    (entmake (list (cons 0 "LAYER")
                   (cons 100 "AcDbSymbolTableRecord")
                   (cons 100 "AcDbLayerTableRecord")
                   (cons 2 name)
                   (cons 70 0)
                   (cons 62 color)
                   (cons 6 "CONTINUOUS"))))
  t)


;;; ============================================================
;;;  配对嵌合 (pair-first)
;;;  思路：对 bbox 相近的复杂件，旋转180°嵌合成"超单元"再排。
;;;  配对在 nest-pack 之前完成，排样器本身不动。
;;; ============================================================

;; 线段相交（含端点接触）
(defun nest-seg-intersect (p1 p2 p3 p4 / o1 o2 o3 o4)
  (defun nest-orient (a b c)
    (- (* (- (car b) (car a)) (- (cadr c) (cadr a)))
       (* (- (cadr b) (cadr a)) (- (car c) (car a)))))
  (defun nest-on-seg (p a b / eps)
    (setq eps 1e-6)
    (and (<= (min (car a) (car b)) (+ (car p) eps))
         (<= (- (car p) eps) (max (car a) (car b)))
         (<= (min (cadr a) (cadr b)) (+ (cadr p) eps))
         (<= (- (cadr p) eps) (max (cadr a) (cadr b)))
         (< (abs (nest-orient a b p)) 1e-4)))
  (setq o1 (nest-orient p1 p2 p3)
        o2 (nest-orient p1 p2 p4)
        o3 (nest-orient p3 p4 p1)
        o4 (nest-orient p3 p4 p2))
  (or (and (< (* o1 o2) 0) (< (* o3 o4) 0))
      (nest-on-seg p3 p1 p2)
      (nest-on-seg p4 p1 p2)
      (nest-on-seg p1 p3 p4)
      (nest-on-seg p2 p3 p4)))

;; 点在多边形内（射线法）
(defun nest-pt-in-polygon (pt poly / n i j xi yi xj yj x0 y0 inside)
  (setq n (length poly) x0 (car pt) y0 (cadr pt) inside nil i 0 j (1- n))
  (while (< i n)
    (setq xi (car (nth i poly)) yi (cadr (nth i poly))
          xj (car (nth j poly)) yj (cadr (nth j poly)))
    (if (and (or (and (<= yi y0) (> yj y0)) (and (> yi y0) (<= yj y0)))
             (< x0 (+ xj (* (- y0 yj) (/ (- xi xj) (- yi yj))))))
      (setq inside (not inside)))
    (setq j i i (1+ i)))
  inside)

;; 多边形是否相交（线段相交 或 点在对方内部）
(defun nest-poly-collide (p1 p2 / n m i j hit)
  (setq n (length p1) m (length p2) hit nil i 0)
  (while (and (< i n) (not hit))
    (setq j 0)
    (while (and (< j m) (not hit))
      (if (nest-seg-intersect (nth i p1) (nth (rem (1+ i) n) p1)
                              (nth j p2) (nth (rem (1+ j) m) p2))
        (setq hit T))
      (setq j (1+ j)))
    (setq i (1+ i)))
  (if hit T
    (progn
      (setq i 0)
      (while (and (< i n) (not hit))
        (if (nest-pt-in-polygon (nth i p1) p2) (setq hit T))
        (setq i (1+ i)))
      (if (not hit)
        (progn
          (setq i 0)
          (while (and (< i m) (not hit))
            (if (nest-pt-in-polygon (nth i p2) p1) (setq hit T))
            (setq i (1+ i)))))
      hit)))

;; 多边形 bbox
(defun nest-poly-bbox (pts / xs ys)
  (setq xs (mapcar 'car pts) ys (mapcar 'cadr pts))
  (list (apply 'min xs) (apply 'min ys) (apply 'max xs) (apply 'max ys)))

;; 平移/旋转点集
(defun nest-translate-pts (pts dx dy / out)
  (setq out nil)
  (foreach p pts (setq out (cons (list (+ (car p) dx) (+ (cadr p) dy)) out)))
  (reverse out))

(defun nest-rotate-pts (pts cx cy ang / c s out dx dy)
  (setq c (cos ang) s (sin ang) out nil)
  (foreach p pts
    (setq dx (- (car p) cx) dy (- (cadr p) cy))
    (setq out (cons (list (+ cx (- (* dx c) (* dy s)))
                          (+ cy (+ (* dx s) (* dy c)))) out)))
  (reverse out))

;; 点集中心
(defun nest-pts-center (pts / bb)
  (setq bb (nest-poly-bbox pts))
  (list (* 0.5 (+ (car bb) (caddr bb)))
        (* 0.5 (+ (cadr bb) (cadddr bb)))))

;; 等距抽稀：把闭合点列均匀抽到 n 点（用于顶点过多的 POLYLINE）
(defun nest-decimate (pts n / m out i idx)
  (setq m (length pts) out nil i 0)
  (while (< i n)
    (setq idx (fix (* i (/ m n))))
    (if (< idx m)
      (setq out (cons (nth idx pts) out)))
    (setq i (1+ i)))
  (reverse out))

;; 点到线段距离
(defun nest-pt-seg-dist (pt a b / dx dy t qx qy)
  (setq dx (- (car b) (car a)) dy (- (cadr b) (cadr a)))
  (if (and (< (abs dx) 1e-9) (< (abs dy) 1e-9))
    (distance pt a)
    (progn
      (setq t (/ (+ (* (- (car pt) (car a)) dx)
                    (* (- (cadr pt) (cadr a)) dy))
                 (+ (* dx dx) (* dy dy))))
      (if (< t 0.0) (setq t 0.0))
      (if (> t 1.0) (setq t 1.0))
      (setq qx (+ (car a) (* t dx)) qy (+ (cadr a) (* t dy)))
      (distance pt (list qx qy)))))

;; 两多边形最小距离（碰撞=0，分离=正距离）
(defun nest-poly-dist (p1 p2 / n m i j d dmin)
  (setq n (length p1) m (length p2) dmin 1e12)
  (setq i 0)
  (while (< i n)
    (setq j 0)
    (while (< j m)
      ;; 点-边距离
      (setq d (nest-pt-seg-dist (nth i p1) (nth j p2) (nth (rem (1+ j) m) p2)))
      (if (< d dmin) (setq dmin d))
      (setq d (nest-pt-seg-dist (nth j p2) (nth i p1) (nth (rem (1+ i) n) p1)))
      (if (< d dmin) (setq dmin d))
      (setq j (1+ j)))
    (setq i (1+ i)))
  dmin)

;; 两多边形是否"碰撞"：距离 < sp 视为碰撞（精确判定）。
;; 因采样/抽稀会低估凹处距离，放大一点间距作为安全余量，
;; 保证实际轮廓间距 >= sp。
(defun nest-poly-hit (p1 p2 sp)
  (or (nest-poly-collide p1 p2)
      (< (nest-poly-dist p1 p2) (* sp 1.3))))

;; ---- 外轮廓采样：取单元中 bbox 面积最大的闭合曲线实体 ----
;; 对 POLYLINE 直接取全部顶点（保留凹处细节，保证间距判定准确）；
;; 其它曲线（ARC/SPLINE/CIRCLE）沿曲线采样。
(defun nest-curve-sample (e n / typ obj pts i p vlist)
  (setq typ (cdr (assoc 0 (entget e))))
  (if (member typ '("LWPOLYLINE" "POLYLINE"))
    (progn
      (setq pts nil)
      (if (= typ "LWPOLYLINE")
        (progn
          (setq obj (vlax-ename->vla-object e))
          (setq vlist (vlax-get obj 'Coordinates))
          (setq i 0)
          (while (< i (length vlist))
            (setq pts (cons (list (nth i vlist) (nth (1+ i) vlist)) pts))
            (setq i (+ i 2))))
        (progn
          ;; 老式 POLYLINE：遍历 VERTEX
          (setq ent e)
          (while (setq ent (entnext ent))
            (setq d (entget ent))
            (if (= (cdr (assoc 0 d)) "VERTEX")
              (setq pts (cons (list (cadr (assoc 10 d)) (caddr (assoc 10 d))) pts))
              (if (= (cdr (assoc 0 d)) "SEQEND") (setq ent nil)))))
        )
      ;; 去重首尾闭合点
      (if (and pts (equal (car pts) (last pts) 1e-6))
        (setq pts (reverse (cdr (reverse pts)))))
      ;; 顶点过多时等距抽稀到 *NEST-PAIR-SAMPLES* 点（保形但控速度）
      (if (> (length pts) *NEST-PAIR-SAMPLES*)
        (setq pts (nest-decimate pts *NEST-PAIR-SAMPLES*)))
      (reverse pts))
    (progn
      ;; 其它曲线：沿曲线采样 n 点
      (setq obj (vlax-ename->vla-object e))
      (setq len (vlax-curve-getdistatparam obj (vlax-curve-getendparam obj)))
      (setq pts nil i 0)
      (while (< i n)
        (setq p (vlax-curve-getpointatdist obj (* len (/ i n))))
        (setq pts (cons (list (car p) (cadr p)) pts))
        (setq i (1+ i)))
      (reverse pts))))

(defun nest-unit-spts (unit / enames best bestarea e obj mn mx w h area res)
  (setq enames (cdr (assoc 'enames unit)) best nil bestarea -1.0)
  (foreach e enames
    (setq obj (vlax-ename->vla-object e))
    (if obj
      (progn
        (setq res (vl-catch-all-apply 'vla-getboundingbox (list obj 'mn 'mx)))
        (if (not (vl-catch-all-error-p res))
          (progn
            (setq mn (vlax-safearray->list mn) mx (vlax-safearray->list mx)
                  w (- (car mx) (car mn)) h (- (cadr mx) (cadr mn))
                  area (* w h))
            (if (> area bestarea)
              (setq bestarea area best e)))))))
  (if best
    (nest-curve-sample best *NEST-PAIR-SAMPLES*)
    nil))

;; ---- 滑动找最小组合 bbox（保留 sp 间距） ----
;; 固定 A（归一化到 A 的真实 bbox 左下角），B 旋转180后从右向左二分滑动，
;; 找刚不碰撞的 x，再遍历 y 找最小组合 bbox。
;; 返回 (cw ch aox aoy box boy)：
;;   cw,ch   = 超单元 bbox 宽高
;;   aox,aoy = A 相对超单元 bbox 左下角的偏移（=0,0，因 A 即超单元原点）
;;   box,boy = B 相对超单元 bbox 左下角的偏移
(defun nest-pair-nest (spts-a spts-b oxa oya oxb oyb aw ah bw bh sp quick /
                       ab A B bb B0 ylo yhi ystep y x best bx by
                       cw ch minx miny maxx maxy)
  (setq A (nest-translate-pts spts-a (- oxa) (- oya))
        B (nest-rotate-pts spts-b (car (nest-pts-center spts-b))
                           (cadr (nest-pts-center spts-b)) pi)
        B0 (nest-translate-pts B (- oxb) (- oyb))
        ylo (- ah) yhi ah
        ystep (if quick 10 5)
        y ylo
        best nil)
  ;; 粗扫：对每个 y，二分找 B 刚不碰 A 的 x，记录组合 bbox 面积最小者
  (while (<= y yhi)
    (setq x (nest-pair-slide A B0 aw sp y))
    (if x
      (progn
        (setq minx (min 0 x) miny (min 0 y)
              maxx (max aw (+ x bw)) maxy (max ah (+ y bh)))
        (setq cw (- maxx minx) ch (- maxy miny))
        (if (or (null best) (< (* cw ch) (car best)))
          (setq best (list (* cw ch) x y)))))
    (setq y (+ y ystep)))
  (if (null best) nil
    (progn
      ;; 局部精扫：在最佳 (x,y) 周围 ±4 步长 1
      (setq bx (cadr best) by (caddr best) y (- by 4))
      (while (<= y (+ by 4))
        (setq x (- bx 4))
        (while (<= x (+ bx 4))
          (if (not (nest-poly-hit A (nest-translate-pts B0 x y) sp))
            (progn
              (setq minx (min 0 x) miny (min 0 y)
                    maxx (max aw (+ x bw)) maxy (max ah (+ y bh)))
              (setq cw (- maxx minx) ch (- maxy miny))
              (if (< (* cw ch) (car best))
                (setq best (list (* cw ch) x y)))))
          (setq x (+ x 1)))
        (setq y (+ y 1)))
      ;; 计算 A/B 在最佳位 (bx,by) 相对超单元 bbox 左下角的偏移
      (setq bx (cadr best) by (caddr best))
      (setq minx (min 0 bx) miny (min 0 by)
            maxx (max aw (+ bx bw)) maxy (max ah (+ by bh)))
      (list (- maxx minx) (- maxy miny)
            (- 0 minx) (- 0 miny)         ; A 偏移
            (- bx minx) (- by miny)))))   ; B 偏移

;; 二分滑动：在给定 y 下，找 B 刚不与 A 碰撞的最小 x（含 sp 间距）。
;; B 从左侧(bw 深重叠)扫到右侧(至少 sp 间隙)，单调 T->F，二分取边界。
(defun nest-pair-slide (A B0 aw sp y / bb bw lo hi mid hit)
  (setq bb (nest-poly-bbox B0)
        bw (- (caddr bb) (car bb))
        lo (- bw)              ; B 左边缘在 -bw，B 覆盖 [-bw,0]，与 A 深重叠
        hi (+ aw (* 2 sp)))    ; B 左边缘在 aw+2sp，距 A > sp，必不碰撞
  (repeat 15
    (setq mid (* 0.5 (+ lo hi)))
    (if (nest-poly-hit A (nest-translate-pts B0 mid y) sp)
      (setq lo mid)
      (setq hi mid)))
  hi)

;; ---- 主配对：对 bbox 相近的复杂件尝试嵌合 ----
;; 用"尺寸池"减少 O(n²)：仅对 bbox 尺寸相近(±15mm)的候选两两尝试。
;; 按 bbox 面积取前 N 个（配对候选超限时用）
(defun subseq-sorted (lst n / s out i)
  (setq s (vl-sort lst
                   '(lambda (a b)
                      (> (* (caddr a) (cadddr a))
                         (* (caddr b) (cadddr b)))))
        out nil i 0)
  (while (and (< i n) s)
    (setq out (cons (car s) out) s (cdr s) i (1+ i)))
  (reverse out))

(defun nest-pair-units (units sp win / cands used-units n i j a b fill
                        bb poly spts res cw ch base gain supers unmatched tries)
  ;; 候选：只对复杂件（bbox 填充率低）采样
  (setq cands nil)
  (foreach u units
    (setq bb (list (cdr (assoc 'w u)) (cdr (assoc 'h u))))
    (setq spts (nest-unit-spts u))
    (if (and spts (>= (length spts) 8))
      (progn
        (setq poly (nest-shoelace spts)
              fill (/ poly (max (* (car bb) (cadr bb)) 1e-9)))
        (if (and (< fill *NEST-PAIR-FILL-MAX*)
                 (> poly 100.0))   ; 过滤采样退化的线/极小件
          (setq cands (cons (list u spts (car bb) (cadr bb)) cands))))))
  (setq cands (reverse cands))
  ;; 候选过多时按 bbox 面积取前 N（防 LISP 卡死）
  (if (> (length cands) *NEST-PAIR-MAX-CAND*)
    (setq cands
          (subseq-sorted cands *NEST-PAIR-MAX-CAND*)))  ;; 按 bbox 周长排序，使相似尺寸相邻，滑动窗口只扫近邻，降低 O(n^2)
  (setq cands
        (vl-sort cands
                 '(lambda (a b)
                    (< (+ (caddr a) (cadddr a))
                       (+ (caddr b) (cadddr b))))))
  (setq used-units nil supers nil n (length cands) i 0
        tries 0)
  (while (and (< i n) (< tries *NEST-PAIR-MAX-TRY*))
    (if (not (member (nth 0 (nth i cands)) used-units))
      (progn
        (setq j (1+ i))
        (while (and (< j n) (< tries *NEST-PAIR-MAX-TRY*)
                    (<= (+ (caddr (nth j cands)) (cadddr (nth j cands)))
                        (+ (caddr (nth i cands)) (cadddr (nth i cands))) 30))
          (setq a (nth i cands) b (nth j cands))
          (if (and (not (member (nth 0 b) used-units))
                   (<= (abs (- (caddr a) (caddr b))) 15)
                   (<= (abs (- (cadddr a) (cadddr b))) 15))
            (progn
              (setq tries (1+ tries))
              (setq res (nest-pair-nest
                          (cadr a) (cadr b)
                          (cdr (assoc 'ox (nth 0 a)))
                          (cdr (assoc 'oy (nth 0 a)))
                          (cdr (assoc 'ox (nth 0 b)))
                          (cdr (assoc 'oy (nth 0 b)))
                          (caddr a) (cadddr a)
                          (caddr b) (cadddr b)
                          sp T))
              (if res
                (progn
                  (setq cw (nth 0 res) ch (nth 1 res))
                  (setq base (+ (* (caddr a) (cadddr a))
                                (* (caddr b) (cadddr b))))
                  (setq gain (- 1 (/ (* cw ch) base)))
                  (if (>= gain (/ win 100.0))
                    (progn
                      (setq supers (cons (nest-make-superunit
                                           (nth 0 a) (nth 0 b)
                                           cw ch
                                           (nth 2 res) (nth 3 res)
                                           (nth 4 res) (nth 5 res))
                                         supers))
                      (setq used-units (cons (nth 0 a) used-units))
                      (setq used-units (cons (nth 0 b) used-units))))))))
          (setq j (1+ j)))))
    (setq i (1+ i)))
  ;; 未配对件：所有未进超单元的原始单元（含矩形件，绝不可丢）
  (setq unmatched nil)
  (foreach u units
    (if (not (member u used-units))
      (setq unmatched (cons u unmatched))))
  (list (append supers (reverse unmatched)) (length supers)))

;; 面积（鞋带公式）
(defun nest-shoelace (pts / n i j area)  (setq n (length pts) area 0.0 i 0)
  (while (< i n)
    (setq j (rem (1+ i) n))
    (setq area (+ area (- (* (car (nth i pts)) (cadr (nth j pts)))
                          (* (car (nth j pts)) (cadr (nth i pts))))))
    (setq i (1+ i)))
  (abs (* 0.5 area)))

;; 生成超单元记录：
;;   (enames nil) (w) (h) (ox) (oy) (n 2) (parts ((unit dx dy rot180) ...))
;; parts 记录每个子单元：相对超单元 bbox 左下角的偏移，以及是否需 180° 旋转
(defun nest-make-superunit (ua ub cw ch aox aoy box boy / pa pb)
  ;; A 固定在超单元原点(即 A 原 bbox 左下角)，B 平移并旋转180°到组合位。
  ;; 记录子件相对超单元 bbox 左下角的世界偏移，及是否需 180° 旋转。
  ;; 超单元 bbox 左下角 = A 世界 bbox 左下角 + (minx,miny)，其中 aox=-minx。
  (setq pa (list ua aox aoy nil)   ; (unit dx dy rot180)
        pb (list ub box boy T))
  (list (cons 'enames nil)
        (cons 'w cw)
        (cons 'h ch)
        (cons 'ox (- (cdr (assoc 'ox ua)) aox))
        (cons 'oy (- (cdr (assoc 'oy ua)) aoy))
        (cons 'n 2)
        (cons 'parts (list pa pb))))

;; 超单元移动：每个子件先旋转180°（若配对时旋转了），再按自身 bbox 左下角
;; 移动到"超单元放置点 + 子件偏移"
(defun nest-move-superunit (unit base bx-on by-on rot / parts u uox uoy
                            dx dy res pdx pdy rot180 px py)
  (setq parts (cdr (assoc 'parts unit))
        px (+ (car base) bx-on)
        py (+ (cadr base) by-on))
  ;; 超单元整体不允许旋转（配对所确定的相对方向已是最优），忽略 rot
  (foreach p parts
    (setq u (car p) pdx (cadr p) pdy (caddr p)
          rot180 (cadddr p)
          uox (cdr (assoc 'ox u))
          uoy (cdr (assoc 'oy u))
          dx (+ px pdx)
          dy (+ py pdy))
    (foreach e (cdr (assoc 'enames u))
      (setq res
            (vl-catch-all-apply
              'nest-move-super-one
              (list e uox uoy rot180 dx dy)))
      (if (vl-catch-all-error-p res)
        (princ (strcat "\n[NEST] super move fail: "
                       (vl-catch-all-error-message res)))))))

;; 子件移动：rot180 时先绕自身 bbox 中心旋转180°，再平移
(defun nest-move-super-one (e uox uoy rot180 dx dy / obj mn mx ctr)
  (if (and e (entget e))
    (progn
      (setq obj (vlax-ename->vla-object e))
      (if rot180
        (progn
          (vla-getboundingbox obj 'mn 'mx)
          (setq mn (vlax-safearray->list mn) mx (vlax-safearray->list mx)
                ctr (vlax-3d-point
                      (list (* 0.5 (+ (car mn) (car mx)))
                            (* 0.5 (+ (cadr mn) (cadr mx)))
                            0.0)))
          (vla-rotate obj ctr pi)))
      (vla-move obj (vlax-3d-point (list uox uoy 0.0))
                    (vlax-3d-point (list dx dy 0.0))))))

(princ "\n[NEST] loaded. Command: NS  (or NEST)")
(princ "\n[NEST] only use: (load \"D:/NEST.LSP\")")
(princ)
