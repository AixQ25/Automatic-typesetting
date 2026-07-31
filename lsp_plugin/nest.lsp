;;; ============================================================
;;;  NEST v20260731-0855  -  AutoCAD 2007 / Win7 32bit
;;;  ONLY load:  (load "D:/NEST.LSP")
;;;  then type:  NEST
;;;  Verify load message: [NEST] loaded. Command: NEST
;;; ============================================================

(vl-load-com)

;;; ---------- 默认参数 ----------
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


;;; ---------- 主命令 ----------
(defun C:NEST ( / *error* ss ents units bbox base-x base-y placements nboards oldcmd)
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


;;; ---------- 提取：VLA bbox，保留 ename ----------
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


;;; ---------- 几何 ----------
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


;;; ---------- 整体识别：包含 + 邻近 并查集 ----------
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


;;; ---------- 排样 ----------
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
                        minx miny maxx maxy out newrem rec w h p1 p rot)
  (setq minx mg miny mg
        maxx (- bw mg) maxy (- bh mg)
        out '() newrem '())
  (foreach rec remaining
    (setq w (cdr (assoc 'w rec))
          h (cdr (assoc 'h rec))
          p1 (nest-find-pos w h minx miny maxx maxy sp out))
    (if p1
      (setq p p1 rot nil)
      (progn
        (setq p1 (nest-find-pos h w minx miny maxx maxy sp out))
        (if p1 (setq p p1 rot T) (setq p nil))))
    (if p
      (setq out (cons (list rec (car p) (cadr p) rot) out))
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
  (setq cands
        (vl-sort cands
                 '(lambda (a b)
                    (or (< (car a) (car b))
                        (and (equal (car a) (car b) *NEST-EPS*)
                             (< (cadr a) (cadr b)))))))
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


;;; ---------- 画板 + 移动原实体 ----------
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

(defun nest-move-unit (unit base bx-on by-on rot /
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


;;; ---------- 图层 ----------
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

(princ "\n[NEST] loaded. Command: NEST")
(princ "\n[NEST] only use: (load \"D:/NEST.LSP\")")
(princ)
