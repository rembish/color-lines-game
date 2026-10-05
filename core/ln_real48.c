/* Turbo Pascal's 6-byte Real, transliterated from the System unit in LINES.EXE (27da:0980 to
 * 0c47) register by register, so that results, truncation and rounding are the original's.
 *
 * A Real is AL (exponent, bias 0x81, 0 = zero), AH (lowest mantissa byte), BX, DX (top word,
 * bit 15 the sign, the leading 1 implicit). The first operand is in AX:BX:DX, the second in
 * CX:SI:DI, as there. Overflow is not handled (the game never overflows); see re/NOTES.md. */
#include "ln_real48.h"

typedef struct {
    uint16_t ax, bx, cx, dx, si, di, bp;
    int cf;
} regs;

#define AL(r)     ((uint8_t)((r).ax & 0xff))
#define AH(r)     ((uint8_t)((r).ax >> 8))
#define SET_AL(r, v) ((r).ax = (uint16_t)(((r).ax & 0xff00) | ((v) & 0xff)))
#define SET_AH(r, v) ((r).ax = (uint16_t)(((r).ax & 0x00ff) | (((v) & 0xff) << 8)))
#define CL(r)     ((uint8_t)((r).cx & 0xff))
#define CH(r)     ((uint8_t)((r).cx >> 8))
#define SET_CL(r, v) ((r).cx = (uint16_t)(((r).cx & 0xff00) | ((v) & 0xff)))
#define SET_CH(r, v) ((r).cx = (uint16_t)(((r).cx & 0x00ff) | (((v) & 0xff) << 8)))
#define BL(r)     ((uint8_t)((r).bx & 0xff))
#define BH(r)     ((uint8_t)((r).bx >> 8))
#define DL(r)     ((uint8_t)((r).dx & 0xff))
#define DH(r)     ((uint8_t)((r).dx >> 8))

static ln_real pack(const regs *r)
{
    ln_real x = { { (uint8_t)(r->ax & 0xff), (uint8_t)(r->ax >> 8), (uint8_t)(r->bx & 0xff),
                    (uint8_t)(r->bx >> 8), (uint8_t)(r->dx & 0xff), (uint8_t)(r->dx >> 8) } };
    return x;
}

static void load(regs *r, ln_real a, ln_real b)
{
    r->ax = (uint16_t)(a.b[0] | a.b[1] << 8);
    r->bx = (uint16_t)(a.b[2] | a.b[3] << 8);
    r->dx = (uint16_t)(a.b[4] | a.b[5] << 8);
    r->cx = (uint16_t)(b.b[0] | b.b[1] << 8);
    r->si = (uint16_t)(b.b[2] | b.b[3] << 8);
    r->di = (uint16_t)(b.b[4] | b.b[5] << 8);
    r->cf = 0;
}

/* 40-bit mantissa helpers on (dx:bx:ah) and (di:si:ch) */
static void shr_dxbxah(regs *r) /* shr dx,1; rcr bx,1; rcr ah,1 */
{
    unsigned c = r->dx & 1;
    r->dx >>= 1;
    unsigned c2 = r->bx & 1;
    r->bx = (uint16_t)(r->bx >> 1 | c << 15);
    unsigned ah = AH(*r);
    r->cf = (int)(ah & 1);
    SET_AH(*r, ah >> 1 | c2 << 7);
}

static void rcr_dxbxah(regs *r) /* rcr dx,1; rcr bx,1; rcr ah,1 (carry in) */
{
    unsigned c = (unsigned)r->cf;
    unsigned c1 = r->dx & 1;
    r->dx = (uint16_t)(r->dx >> 1 | c << 15);
    unsigned c2 = r->bx & 1;
    r->bx = (uint16_t)(r->bx >> 1 | c1 << 15);
    unsigned ah = AH(*r);
    r->cf = (int)(ah & 1);
    SET_AH(*r, ah >> 1 | c2 << 7);
}

static void rcl_ahbxdx(regs *r) /* rcl ah,1; rcl bx,1; rcl dx,1 (carry in) */
{
    unsigned c = (unsigned)r->cf;
    unsigned ah = AH(*r);
    unsigned c1 = ah >> 7;
    SET_AH(*r, ah << 1 | c);
    unsigned c2 = r->bx >> 15;
    r->bx = (uint16_t)(r->bx << 1 | c1);
    r->cf = (int)(r->dx >> 15);
    r->dx = (uint16_t)(r->dx << 1 | c2);
}

static void add40(regs *r) /* add ah,ch; adc bx,si; adc dx,di */
{
    unsigned s = AH(*r) + CH(*r);
    SET_AH(*r, s);
    unsigned long t = (unsigned long)r->bx + r->si + (s >> 8);
    r->bx = (uint16_t)t;
    unsigned long u = (unsigned long)r->dx + r->di + (t >> 16);
    r->dx = (uint16_t)u;
    r->cf = (int)(u >> 16);
}

static void sub40(regs *r) /* sub ah,ch; sbb bx,si; sbb dx,di */
{
    int s = AH(*r) - CH(*r);
    SET_AH(*r, s);
    long t = (long)r->bx - r->si - (s < 0);
    r->bx = (uint16_t)t;
    long u = (long)r->dx - r->di - (t < 0);
    r->dx = (uint16_t)u;
    r->cf = u < 0;
}

/* 27da:0984 (add); 0980 flips the second operand's sign first (subtract) */
static void add(regs *r)
{
    if (CL(*r) == 0) return;
    if (AL(*r) == 0) {
        r->ax = r->cx, r->bx = r->si, r->dx = r->di;
        return;
    }
    if (AL(*r) > CL(*r)) { /* the smaller exponent into AX:BX:DX */
        uint16_t t;
        t = r->ax, r->ax = r->cx, r->cx = t;
        t = r->bx, r->bx = r->si, r->si = t;
        t = r->dx, r->dx = r->di, r->di = t;
    }
    unsigned diff = (uint8_t)(CL(*r) - AL(*r));
    if (diff >= 0x28) {
        r->ax = r->cx, r->bx = r->si, r->dx = r->di;
        return;
    }
    SET_AL(*r, CL(*r)); /* xchg cl,al */
    SET_CL(*r, diff);
    uint16_t saved_bp = r->bp;
    int differ = ((r->di ^ r->dx) & 0x8000) != 0;
    r->bp = r->di;
    r->dx |= 0x8000;
    r->di |= 0x8000;
    while (CL(*r) >= 0x10) {
        SET_AH(*r, BH(*r));
        r->bx = r->dx;
        r->dx = 0;
        SET_CL(*r, CL(*r) - 0x10);
    }
    if (CL(*r) >= 8) {
        SET_AH(*r, BL(*r));
        r->bx = (uint16_t)(BH(*r) | DL(*r) << 8);
        r->dx = DH(*r);
        SET_CL(*r, CL(*r) - 8);
    }
    for (unsigned n = CL(*r); n; n--) shr_dxbxah(r);
    if (!differ) {
        add40(r);
        if (r->cf) {
            rcr_dxbxah(r);
            SET_AL(*r, AL(*r) + 1);
        }
    } else {
        uint16_t t;
        unsigned c = CH(*r);
        SET_CH(*r, AH(*r));
        SET_AH(*r, c);
        t = r->si, r->si = r->bx, r->bx = t;
        t = r->di, r->di = r->dx, r->dx = t;
        sub40(r);
        if (r->cf) {
            r->bp ^= 0x8000;
            SET_AH(*r, ~AH(*r));
            r->bx = (uint16_t)~r->bx;
            r->dx = (uint16_t)~r->dx;
            unsigned s = AH(*r) + 1u;
            SET_AH(*r, s);
            unsigned long u = (unsigned long)r->bx + (s >> 8);
            r->bx = (uint16_t)u;
            r->dx = (uint16_t)(r->dx + (u >> 16));
        }
        /* normalise (0a1e) */
        int zero = 0;
        for (unsigned n = 5; DH(*r) == 0;) {
            r->dx = (uint16_t)(DL(*r) << 8 | BH(*r));
            r->bx = (uint16_t)(BL(*r) << 8 | AH(*r));
            SET_AH(*r, 0);
            if (AL(*r) <= 8) {
                zero = 1;
                break;
            }
            SET_AL(*r, AL(*r) - 8);
            if (--n == 0) {
                zero = 1;
                break;
            }
        }
        while (!zero && !(DH(*r) & 0x80)) {
            r->cf = 0;
            rcl_ahbxdx(r);
            SET_AL(*r, AL(*r) - 1);
            if (AL(*r) == 0) zero = 1;
        }
        if (zero) {
            r->ax = r->bx = r->dx = 0;
            r->bp = saved_bp;
            return;
        }
    }
    r->dx = (uint16_t)((r->dx & 0x7fff) ^ (r->bp & 0x8000));
    r->bp = saved_bp;
}

/* 27da:0b60: the exponent after a multiply or divide (carry from the exponent arithmetic in),
 * the sign of the result into CL; returns 0 for an underflow (zero result) */
static int exponent(regs *r, int carry)
{
    unsigned al = AL(*r) + 0x80u;
    SET_AL(*r, al);
    if (!carry) {
        if (!(al >> 8)) {
            r->ax = r->bx = r->dx = 0;
            return 0;
        }
    }
    /* xchg di,ax: AH is the second operand's top byte */
    unsigned sign = (unsigned)~((r->di >> 8) ^ DH(*r)) & 0x80u;
    SET_CL(*r, sign);
    r->di |= 0x8000;
    r->dx |= 0x8000;
    return 1;
}

/* 27da:0a5a */
static void mul(regs *r)
{
    if (CL(*r) == 0) {
        r->ax = r->bx = r->dx = 0;
        return;
    }
    if (AL(*r) == 0) return;
    unsigned e = AL(*r) + CL(*r);
    SET_AL(*r, e);
    if (!exponent(r, (int)(e >> 8))) return;
    /* push ax, di, si, cx: the multiplier's bytes and the sign */
    uint8_t stack[8] = { CL(*r), CH(*r), (uint8_t)(r->si & 0xff), (uint8_t)(r->si >> 8),
                         (uint8_t)(r->di & 0xff), (uint8_t)(r->di >> 8), AL(*r), AH(*r) };
    SET_CH(*r, AH(*r));
    r->si = r->bx;
    r->di = r->dx;
    SET_AH(*r, 0);
    r->bx = r->dx = 0;
    r->cf = 0;
    for (int k = 1; k <= 5; k++) {
        unsigned m = stack[k];
        if (m == 0) {
            SET_AH(*r, BL(*r));
            r->bx = (uint16_t)(BH(*r) | DL(*r) << 8);
            r->dx = DH(*r);
            continue;
        }
        r->cf = 0;
        for (int n = 0; n < 8; n++) {
            unsigned bit = m & 1; /* rcr al,1 */
            m = m >> 1 | (unsigned)r->cf << 7;
            r->cf = (int)bit;
            if (bit) add40(r);
            rcr_dxbxah(r);
        }
        SET_CL(*r, r->cf); /* rcl cl,1 with cl = 0 */
    }
    SET_AL(*r, stack[6]);
    if (!(DH(*r) & 0x80)) {
        r->cf = CL(*r) & 1; /* rcr cl,1 */
        rcl_ahbxdx(r);
        if (AL(*r)) SET_AL(*r, AL(*r) - 1);
    }
    r->dx ^= (uint16_t)(stack[0] << 8);
    if (AL(*r) == 0) r->ax = r->bx = r->dx = 0;
}

static int cmp40(const regs *r) /* the compare in 0af0 / 0b2d: dx:bx:ah below di:si:ch */
{
    if (r->dx != r->di) return r->dx < r->di;
    if (r->bx != r->si) return r->bx < r->si;
    return AH(*r) < CH(*r);
}

/* 27da:0ad7 (CL is not zero: 0c60 checks), its jumps kept as they are */
static void divide(regs *r)
{
    if (AL(*r) == 0) return;
    int borrow = AL(*r) < CL(*r);
    SET_AL(*r, AL(*r) - CL(*r));
    if (!exponent(r, !borrow)) return; /* cmc before the call */
    /* push cx; sub sp,4; push ax: mem[0..1] = AX, mem[2..5] the quotient's bytes, then CX */
    uint8_t mem[6] = { AL(*r), AH(*r), 0, 0, 0, 0 };
    uint8_t sign = CL(*r);
    unsigned al = AL(*r);
    int bp = 5, cl = 8;
    goto compare;
compare: /* 0af0 */
    if (cmp40(r))
        r->cf = 1;
    else {
        sub40(r);
        r->cf = 0;
    }
    r->cf = !r->cf;
quotient_bit: /* 0b03 */
    al = (al << 1 | (unsigned)r->cf) & 0xff;
    if (--cl == 0) goto store;
shift: /* 0b09 */
    r->cf = 0;
    rcl_ahbxdx(r);
    if (!r->cf) goto compare;
    sub40(r);
    r->cf = 1;
    goto quotient_bit;
store: /* 0b1b */
    mem[bp] = (uint8_t)al;
    cl = 8;
    if (--bp != 0) goto shift;
    /* the next bit, kept in SI's bit 0 */
    r->cf = 0;
    rcl_ahbxdx(r);
    int extra = r->cf ? 1 : !cmp40(r);
    r->ax = (uint16_t)(mem[0] | mem[1] << 8);
    r->bx = (uint16_t)(mem[2] | mem[3] << 8);
    r->dx = (uint16_t)(mem[4] | mem[5] << 8);
    if (DH(*r) & 0x80)
        SET_AL(*r, AL(*r) + 1);
    else {
        r->cf = extra;
        rcl_ahbxdx(r);
    }
    r->dx ^= (uint16_t)(sign << 8);
    if (AL(*r) == 0) r->ax = r->bx = r->dx = 0;
}

ln_real ln_real_add(ln_real a, ln_real b)
{
    regs r = { 0 };
    load(&r, a, b);
    add(&r);
    return pack(&r);
}

ln_real ln_real_sub(ln_real a, ln_real b)
{
    regs r = { 0 };
    load(&r, a, b);
    r.di ^= 0x8000;
    add(&r);
    return pack(&r);
}

ln_real ln_real_mul(ln_real a, ln_real b)
{
    regs r = { 0 };
    load(&r, a, b);
    mul(&r);
    return pack(&r);
}

ln_real ln_real_div(ln_real a, ln_real b)
{
    regs r = { 0 };
    load(&r, a, b);
    divide(&r);
    return pack(&r);
}

/* 27da:0b83: -1, 0, 1 for a below, equal, above b (what jb / je test) */
int ln_real_cmp(ln_real a, ln_real b)
{
    regs r = { 0 };
    load(&r, a, b);
    if ((r.dx ^ r.di) & 0x8000) return (r.dx & 0x8000) ? -1 : 1;
    int c;
    if (AL(r) != CL(r))
        c = AL(r) < CL(r) ? -1 : 1;
    else if (AL(r) == 0)
        c = 0;
    else if (r.dx != r.di)
        c = r.dx < r.di ? -1 : 1;
    else if (r.bx != r.si)
        c = r.bx < r.si ? -1 : 1;
    else if (AH(r) != CH(r))
        c = AH(r) < CH(r) ? -1 : 1;
    else
        c = 0;
    return (r.dx & 0x8000) ? -c : c;
}

/* 27da:0bad */
ln_real ln_real_from_long(int32_t v)
{
    regs r = { 0 };
    r.ax = (uint16_t)((uint32_t)v & 0xffff);
    r.dx = (uint16_t)((uint32_t)v >> 16);
    if (!(r.ax | r.dx)) return pack(&r);
    int negative = (r.dx & 0x8000) != 0;
    if (negative) {
        uint32_t u = (uint32_t)(-(int64_t)v);
        r.ax = (uint16_t)(u & 0xffff);
        r.dx = (uint16_t)(u >> 16);
    }
    r.bx = r.ax;
    r.ax = 0xa0;
    if (r.dx == 0) {
        r.dx = r.bx;
        r.bx = 0;
        r.ax = 0x90;
        if (DH(r) == 0) {
            r.dx = (uint16_t)(r.dx << 8);
            r.ax = 0x88;
        }
    }
    while (!(r.dx & 0x8000)) {
        SET_AL(r, AL(r) - 1);
        unsigned c = r.bx >> 15;
        r.bx = (uint16_t)(r.bx << 1);
        r.dx = (uint16_t)(r.dx << 1 | c);
    }
    if (!negative) r.dx &= 0x7fff;
    return pack(&r);
}

/* 27da:0bec with CH = 1 (Round, 0c7a) or 0 (Trunc, 0c72); out of range gives 0 */
static int32_t to_long(ln_real a, int round)
{
    uint16_t lo = (uint16_t)(a.b[0] | a.b[1] << 8), mid = (uint16_t)(a.b[2] | a.b[3] << 8);
    uint16_t dx = (uint16_t)(a.b[4] | a.b[5] << 8), ax = mid;
    uint8_t e = (uint8_t)(lo & 0xff);
    if (e > 0x9f) return 0;
    unsigned cl = 0x9fu - e;
    if (cl > 0x1f) return 0;
    cl++;
    int negative = (dx & 0x8000) != 0;
    dx |= 0x8000;
    if (cl >= 0x11) {
        ax = dx;
        dx = 0;
        cl -= 16;
    }
    if (cl >= 9) {
        ax = (uint16_t)((ax >> 8) | (dx & 0xff) << 8);
        dx >>= 8;
        cl -= 8;
    }
    unsigned carry = 0;
    for (; cl; cl--) {
        carry = ax & 1;
        ax = (uint16_t)(ax >> 1 | (dx & 1) << 15);
        dx >>= 1;
    }
    uint32_t v = (uint32_t)dx << 16 | ax;
    if (carry && round) v++;
    return negative ? -(int32_t)v : (int32_t)v;
}

int32_t ln_real_round(ln_real a) { return to_long(a, 1); }
int32_t ln_real_trunc(ln_real a) { return to_long(a, 0); }

ln_real ln_real_const(uint16_t cx, uint16_t si, uint16_t di)
{
    ln_real x = { { (uint8_t)(cx & 0xff), (uint8_t)(cx >> 8), (uint8_t)(si & 0xff), (uint8_t)(si >> 8),
                    (uint8_t)(di & 0xff), (uint8_t)(di >> 8) } };
    return x;
}
