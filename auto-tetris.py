import pygame  # pip install pygame
import random  # Libreria standard di Python
import sys     # Libreria standard di Python
import time    # Libreria standard di Python

# Costanti del gioco
CELL_SIZE = 30             # Dimensione di una cella in pixel
COLS = 10                  # Larghezza della board di gioco
ROWS = 20                  # Altezza della board di gioco
WIDTH = COLS * CELL_SIZE   # Larghezza della finestra di gioco
HEIGHT = ROWS * CELL_SIZE  # Altezza della board di gioco
INFO_HEIGHT = 150          # Altezza dell'area informativa (aumentata per mostrare i bottoni)
FPS = 30                   # Frame per secondo

# Colori
COLORS = {
    'I': (0, 240, 240),
    'J': (0, 0, 240),
    'L': (240, 160, 0),
    'O': (240, 240, 0),
    'S': (0, 240, 0),
    'T': (160, 0, 240),
    'Z': (240, 0, 0)
}
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
WHITE = (255, 255, 255)

# Definizione dei tetramini (liste di stringhe)
TETROMINOS = {
    'I': [
        ["....",
         "####",
         "....",
         "...."],
        ["..#.",
         "..#.",
         "..#.",
         "..#."]
    ],
    'J': [
        [".#..",
         ".#..",
         "##..",
         "...."],
        ["#...",
         "###.",
         "....",
         "...."],
        [".##.",
         ".#..",
         ".#..",
         "...."],
        ["###.",
         "..#.",
         "....",
         "...."]
    ],
    'L': [
        [".#..",
         ".#..",
         ".##.",
         "...."],
        ["###.",
         "#...",
         "....",
         "...."],
        ["##..",
         ".#..",
         ".#..",
         "...."],
        ["..#.",
         "###.",
         "....",
         "...."]
    ],
    'O': [
        [".##.",
         ".##.",
         "....",
         "...."]
    ],
    'S': [
        [".##.",
         "##..",
         "....",
         "...."],
        [".#..",
         ".##.",
         "..#.",
         "...."]
    ],
    'T': [
        [".#..",
         "###.",
         "....",
         "...."],
        [".#..",
         ".##.",
         ".#..",
         "...."],
        ["###.",
         ".#..",
         "....",
         "...."],
        [".#..",
         "##..",
         ".#..",
         "...."]
    ],
    'Z': [
        ["##..",
         ".##.",
         "....",
         "...."],
        ["..#.",
         ".##.",
         ".#..",
         "...."]
    ]
}

def rotate_shape(shape, times=1):  # Funzione di utilità per ruotare una shape
    """Ruota la shape di 90° (times volte)."""
    grid = [list(row) for row in shape]
    for _ in range(times):
        grid = [list(row) for row in zip(*grid[::-1])]
    return ["".join(row) for row in grid]

def get_rotations(piece):  # Funzione di utilità per ottenere tutte le rotazioni di un tetramino
    """Restituisce tutte le rotazioni uniche per il tetramino."""
    rotations = []
    for shape in TETROMINOS[piece]:
        if shape not in rotations:
            rotations.append(shape)
    return rotations

class Tetromino:  # Classe per rappresentare un tetramino
    def __init__(self, shape):
        self.shape = shape  # una lettera: 'I', 'J', etc.
        self.rotations = get_rotations(shape)
        self.rotation_index = 0
        self.matrix = self.rotations[self.rotation_index]
        # Posizione iniziale: colonna centrale in alto
        self.x = COLS // 2 - 2
        self.y = 0

    def rotate(self):  # Ruota il pezzo senza controlli; la validità viene verificata successivamente
        """Ruota il pezzo senza controlli; la validità viene verificata successivamente."""
        self.rotation_index = (self.rotation_index + 1) % len(self.rotations)
        self.matrix = self.rotations[self.rotation_index]

    def get_cells(self):  # Restituisce le coordinate delle celle occupate dal pezzo
        """Restituisce una lista di (x, y) per le celle occupate dal pezzo."""
        cells = []
        for dy, row in enumerate(self.matrix):
            for dx, cell in enumerate(row):
                if cell == "#":
                    cells.append((self.x + dx, self.y + dy))
        return cells

class Tetris:  # Classe per rappresentare il gioco di Tetris
    def __init__(self):  # Inizializza il gioco
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.lines_cleared = 0
        self.level = 1
        self.game_over = False
        self.bag = []
        self.current_piece = self.get_new_piece()

    def get_new_piece(self):  # Restituisce un nuovo pezzo usando il sistema 'bag' per la randomizzazione
        """Restituisce un nuovo pezzo usando il sistema 'bag' per la randomizzazione."""
        if not self.bag:
            self.bag = list(TETROMINOS.keys())
            random.shuffle(self.bag)
        shape = self.bag.pop()
        return Tetromino(shape)

    def is_valid_position(self, tetromino, adj_x=0, adj_y=0):  # Verifica se il tetromino può essere posizionato sulla board con gli offset
        """Verifica se il tetromino può essere posizionato sulla board con gli offset."""
        for x, y in tetromino.get_cells():
            x += adj_x
            y += adj_y
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def lock_piece(self, tetromino):  # Fissa il pezzo sulla board e, se necessario, cancella le linee
        """Fissa il pezzo sulla board e, se necessario, cancella le linee."""
        for x, y in tetromino.get_cells():
            if y < 0:
                self.game_over = True
                return
            self.board[y][x] = COLORS[tetromino.shape]
        self.clear_lines()
        self.current_piece = self.get_new_piece()
        # pygame.time.delay(100)  # Pausa opzionale dopo il lock

    def clear_lines(self):  # Cancella le linee complete e aggiorna punteggio e livello
        """Cancella le linee complete e aggiorna punteggio e livello."""
        full_lines = [i for i, row in enumerate(self.board) if None not in row]
        num_lines = len(full_lines)
        if num_lines:
            for i in reversed(full_lines):
                del self.board[i]
                self.board.insert(0, [None for _ in range(COLS)])
            points = {1: 40, 2: 100, 3: 300, 4: 1200}
            self.score += points.get(num_lines, 0) * self.level
            self.lines_cleared += num_lines
            self.level = self.lines_cleared // 10 + 1

    def simulate_drop(self, tetromino):  # Simula il drop del pezzo e restituisce la y finale
        """Simula il drop del pezzo e restituisce la y finale (senza modificarne lo stato permanente)."""
        temp_y = tetromino.y
        while self.is_valid_position(tetromino, adj_y=1):
            tetromino.y += 1
        final_y = tetromino.y
        tetromino.y = temp_y  # ripristina
        return final_y

    def clone_board_after_placement(self, tetromino):  # Restituisce una copia della board dopo aver simulato il drop del pezzo
        """Restituisce una copia della board dopo aver simulato il drop del pezzo."""
        board_copy = [row[:] for row in self.board]
        temp_y = tetromino.y
        while self.is_valid_position(tetromino, adj_y=1):
            tetromino.y += 1
        for x, y in tetromino.get_cells():
            if 0 <= y < ROWS and 0 <= x < COLS:
                board_copy[y][x] = COLORS[tetromino.shape]
        tetromino.y = temp_y
        board_copy = self.clear_lines_in_board(board_copy)
        return board_copy

    def clear_lines_in_board(self, board):  # Cancella le linee complete in una board data e restituisce la board risultante
        """Cancella le linee complete in una board data e restituisce la board risultante."""
        new_board = [row for row in board if None in row]
        lines_cleared = ROWS - len(new_board)
        for _ in range(lines_cleared):
            new_board.insert(0, [None for _ in range(COLS)])
        return new_board

    def get_board_heights(self, board):  # Restituisce una lista con l'altezza di ciascuna colonna
        """Restituisce una lista con l'altezza di ciascuna colonna."""
        heights = [0] * COLS
        for x in range(COLS):
            for y in range(ROWS):
                if board[y][x] is not None:
                    heights[x] = ROWS - y
                    break
        return heights

    def get_board_holes(self, board, heights):  # Conta i buchi (celle vuote sotto un blocco) nella board
        """Conta i buchi (celle vuote sotto un blocco) nella board."""
        holes = 0
        for x in range(COLS):
            block_found = False
            for y in range(ROWS):
                if board[y][x] is not None:
                    block_found = True
                elif block_found:
                    holes += 1
        return holes

    def get_bumpiness(self, heights):  # Calcola la "bumpiness" (somma delle differenze di altezza tra colonne adiacenti)
        bumpiness = 0
        for i in range(len(heights) - 1):
            bumpiness += abs(heights[i] - heights[i + 1])
        return bumpiness

    def count_full_lines(self, board):  # Conta le linee complete nella board
        """Conta le linee complete nella board."""
        return sum(1 for row in board if None not in row)

    def evaluate_board(self, board):  # Valuta la board usando un modello lineare basato su altezza, linee, buchi e bumpiness
        """Valuta la board usando un modello lineare basato su altezza, linee, buchi e bumpiness."""
        heights = self.get_board_heights(board)
        aggregate_height = sum(heights)
        holes = self.get_board_holes(board, heights)
        bumpiness = self.get_bumpiness(heights)
        score = (-0.510066 * aggregate_height) + (0.760666 * self.count_full_lines(board)) \
                - (0.35663 * holes) - (0.184483 * bumpiness)
        return score

    def best_move(self):  # Esplora le rotazioni e posizioni possibili per il pezzo corrente, scegliendo quella che massimizza la valutazione
        """
        Esplora le rotazioni e posizioni possibili per il pezzo corrente, scegliendo quella che massimizza la valutazione.
        Restituisce (rotation_index, x_final).
        """
        best_score = -float("inf")
        best_rotation = 0
        best_x = 0

        original_piece = self.current_piece
        for rotation in range(len(original_piece.rotations)):
            piece = Tetromino(original_piece.shape)
            piece.rotation_index = rotation
            piece.matrix = piece.rotations[rotation]
            cells = self.get_cells_from_matrix(piece.matrix)
            min_x = -min([x for x, _ in cells])
            max_x = COLS - max([x for x, _ in cells])
            for x in range(min_x, max_x):
                piece.x = x
                piece.y = 0
                if not self.is_valid_position(piece):
                    continue
                piece.y = self.simulate_drop(piece)
                board_after = self.clone_board_after_placement(piece)
                score = self.evaluate_board(board_after)
                if score > best_score:
                    best_score = score
                    best_rotation = rotation
                    best_x = x
        return best_rotation, best_x

    def get_cells_from_matrix(self, matrix):  # Restituisce la lista delle coordinate dei blocchi
        """Data una matrice (lista di stringhe), restituisce la lista delle coordinate dei blocchi."""
        cells = []
        for dy, row in enumerate(matrix):
            for dx, ch in enumerate(row):
                if ch == "#":
                    cells.append((dx, dy))
        return cells

    def attempt_rotate_with_wallkick(self, tetromino):  # Prova a ruotare il pezzo; se la rotazione non è valida, prova piccoli spostamenti laterali (wall kick)
        """
        Prova a ruotare il pezzo; se la rotazione non è valida, prova piccoli spostamenti laterali (wall kick).
        Restituisce True se la rotazione ha successo.
        """
        orig_rotation = tetromino.rotation_index
        orig_matrix = tetromino.matrix
        orig_x = tetromino.x

        tetromino.rotate()
        if self.is_valid_position(tetromino):
            return True

        for dx in (1, -1, 2, -2):
            if self.is_valid_position(tetromino, adj_x=dx):
                tetromino.x += dx
                return True

        tetromino.rotation_index = orig_rotation
        tetromino.matrix = orig_matrix
        tetromino.x = orig_x
        return False

def draw_board(screen, board):  # Disegna la board sullo schermo
    """Disegna la board sullo schermo."""
    for y in range(ROWS):
        for x in range(COLS):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if board[y][x]:
                pygame.draw.rect(screen, board[y][x], rect)
            else:
                pygame.draw.rect(screen, GRAY, rect, 1)

def draw_piece(screen, tetromino):  # Disegna il pezzo corrente
    """Disegna il pezzo corrente."""
    for x, y in tetromino.get_cells():
        if y >= 0:
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, COLORS[tetromino.shape], rect)

def draw_info(screen, font, game, start_time):
    """Disegna le informazioni (punteggio, livello, tempo e controlli) in un'area dedicata."""
    info_surface = pygame.Surface((WIDTH, INFO_HEIGHT))
    info_surface.fill(BLACK)
    # Dati di gioco
    score_text = font.render(f"Score: {game.score}", True, WHITE)
    level_text = font.render(f"Livello: {game.level}", True, WHITE)
    elapsed_seconds = (pygame.time.get_ticks() - start_time) // 1000
    time_text = font.render(f"Tempo: {elapsed_seconds}s", True, WHITE)
    info_surface.blit(score_text, (10, 10))
    info_surface.blit(level_text, (10, 40))
    info_surface.blit(time_text, (10, 70))
    # Bottoni/Controlli (disposti verticalmente)
    pause_text = font.render("P: Pausa/Play", True, (200, 200, 0))
    reset_text = font.render("R: Reset", True, (200, 200, 0))
    quit_text = font.render("Q: Esci", True, (200, 200, 0))
    info_surface.blit(pause_text, (WIDTH - pause_text.get_width() - 10, 10))
    info_surface.blit(reset_text, (WIDTH - reset_text.get_width() - 10, 40))
    info_surface.blit(quit_text, (WIDTH - quit_text.get_width() - 10, 70))
    screen.blit(info_surface, (0, HEIGHT))

def draw_pause(screen, font):
    """Disegna il messaggio di pausa al centro dello schermo."""
    pause_text = font.render("PAUSA", True, (255, 255, 0))
    screen.blit(pause_text, (WIDTH // 2 - pause_text.get_width() // 2, HEIGHT // 2 - pause_text.get_height() // 2))

def main():
    pygame.init()  # Inizializza Pygame
    screen = pygame.display.set_mode((WIDTH, HEIGHT + INFO_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Tetris Bot")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 20)
    
    fullscreen = False
    game = Tetris()
    last_drop_time = time.time() * 1000  # Usiamo time.time() invece di pygame.time.get_ticks()
    start_time = pygame.time.get_ticks()
    
    ai_planned = False  # Variabile per tenere traccia se il bot ha già pianificato la mossa
    move_instructions = []  # Istruzioni per il bot
    paused = False  # Stato di pausa
    waiting_to_start = True  # Schermata iniziale
    
    # Schermata iniziale
    while waiting_to_start:
        screen.fill(BLACK)
        text = font.render("Premi un tasto per iniziare", True, WHITE)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, (HEIGHT + INFO_HEIGHT) // 2 - text.get_height() // 2))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                waiting_to_start = False

    while not game.game_over:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((pygame.display.Info().current_w, pygame.display.Info().current_h), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT + INFO_HEIGHT), pygame.RESIZABLE)
                elif event.key == pygame.K_p:  # Pausa/Riprendi
                    paused = not paused
                    if paused:
                        pause_time = pygame.time.get_ticks()
                    else:
                        start_time += pygame.time.get_ticks() - pause_time
                elif event.key == pygame.K_r:  # Reset del gioco
                    game = Tetris()
                    last_drop_time = time.time() * 1000
                    start_time = pygame.time.get_ticks()
                    ai_planned = False
                    move_instructions = []
                    paused = False
                elif event.key == pygame.K_q:  # Esci dal gioco
                    pygame.quit()
                    sys.exit()

        if paused:
            screen.fill(BLACK)
            draw_board(screen, game.board)
            draw_piece(screen, game.current_piece)
            draw_info(screen, font, game, start_time)
            draw_pause(screen, font)
            pygame.display.flip()
            clock.tick(FPS)
            continue

        drop_interval = max(50, 2000 - (game.level - 1) * 150)
        current_time = time.time() * 1000
        
        if not ai_planned:
            best_rotation, best_x = game.best_move()
            move_instructions = []
            current_rotations = game.current_piece.rotation_index
            rotations_needed = (best_rotation - current_rotations) % len(game.current_piece.rotations)
            for _ in range(rotations_needed):
                move_instructions.append("rotate")
            dx = best_x - game.current_piece.x
            if dx > 0:
                move_instructions += ["right"] * dx
            elif dx < 0:
                move_instructions += ["left"] * (-dx)
            move_instructions.append("drop")
            ai_planned = True
        
        if move_instructions:
            pygame.time.delay(50)
            instruction = move_instructions.pop(0)
            if instruction == "rotate":
                game.attempt_rotate_with_wallkick(game.current_piece)
            elif instruction == "left":
                if game.is_valid_position(game.current_piece, adj_x=-1):
                    game.current_piece.x -= 1
            elif instruction == "right":
                if game.is_valid_position(game.current_piece, adj_x=1):
                    game.current_piece.x += 1
            elif instruction == "drop":
                game.current_piece.y = game.simulate_drop(game.current_piece)
                game.lock_piece(game.current_piece)
                ai_planned = False
                move_instructions = []
                last_drop_time = current_time  
        else:
            if current_time - last_drop_time > drop_interval:
                if game.is_valid_position(game.current_piece, adj_y=1):
                    game.current_piece.y += 1
                else:
                    game.lock_piece(game.current_piece)
                    ai_planned = False
                last_drop_time = current_time
        
        screen.fill(BLACK)
        draw_board(screen, game.board)
        draw_piece(screen, game.current_piece)
        draw_info(screen, font, game, start_time)
        pygame.display.flip()
        clock.tick(FPS)
    
    # Schermata di Game Over
    screen.fill(BLACK)
    over_text = font.render("GAME OVER", True, (255, 0, 0))
    final_score_text = font.render(f"Score finale: {game.score}", True, WHITE)
    screen.blit(over_text, (WIDTH // 2 - over_text.get_width() // 2, HEIGHT // 2 - over_text.get_height()))
    screen.blit(final_score_text, (WIDTH // 2 - final_score_text.get_width() // 2, HEIGHT // 2 + 10))
    pygame.display.flip()
    time.sleep(3)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
