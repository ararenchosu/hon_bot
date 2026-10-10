BLACK = "⚫"
WHITE = "⚪"
EMPTY = "⬜"
SIZE = 8

class OthelloBoard:
    def __init__(self):
        self.board = [[EMPTY for _ in range(SIZE)] for _ in range(SIZE)]
        self.board[3][3] = WHITE
        self.board[3][4] = BLACK
        self.board[4][3] = BLACK
        self.board[4][4] = WHITE
        self.current = BLACK  # 黒が先手

    def is_valid_pos(self, r, c):
        return 0 <= r < SIZE and 0 <= c < SIZE

    def get_reverses(self, r, c, color):
        if self.board[r][c] != EMPTY:
            return []
        enemy = WHITE if color == BLACK else BLACK
        dirs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        all_rev = []
        for dr, dc in dirs:
            rr, cc = r+dr, c+dc
            tmp = []
            while self.is_valid_pos(rr, cc) and self.board[rr][cc] == enemy:
                tmp.append((rr, cc))
                rr += dr
                cc += dc
            if tmp and self.is_valid_pos(rr, cc) and self.board[rr][cc] == color:
                all_rev.extend(tmp)
        return all_rev

    def put(self, r, c):
        rev = self.get_reverses(r, c, self.current)
        if not rev:
            return False
        self.board[r][c] = self.current
        for rr, cc in rev:
            self.board[rr][cc] = self.current
        self.current = WHITE if self.current == BLACK else BLACK
        return True

    def can_put(self, color):
        for r in range(SIZE):
            for c in range(SIZE):
                if self.get_reverses(r, c, color):
                    return True
        return False

    def count(self):
        b = sum(row.count(BLACK) for row in self.board)
        w = sum(row.count(WHITE) for row in self.board)
        return b, w

    def is_game_over(self):
        b, w = self.count()
        if b == 0 or w == 0:
            return True
        if not self.can_put(BLACK) and not self.can_put(WHITE):
            return True
        return False

    def render(self):
        lines = ["　ａｂｃｄｅｆｇｈ"]
        for i, row in enumerate(self.board, start=1):
            lines.append(f"{i}　{' '.join(row)}")
        return "\n".join(lines)
