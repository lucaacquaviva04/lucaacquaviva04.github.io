import pygame
import random
from collections import deque
import heapq
import math
import logging
import sys

# Configurazioni base
CELL_SIZE = 20
CELL_NUMBER = 40
WINDOW_SIZE = CELL_SIZE * CELL_NUMBER

# Inizializzazione di Pygame
pygame.init()
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

# Configurazione del logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Colori definiti come costanti
BACKGROUND_COLOR = (175, 215, 70)
TEXT_COLOR = (50, 50, 50)
SNAKE_COLOR = (0, 120, 0)
FOOD_COLOR = (255, 0, 0)


class Snake:
    """
    Classe che rappresenta il serpente e gestisce il suo stato e movimento.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        """Resetta lo stato del serpente (ma non altri parametri di gioco come punteggio o velocità)."""
        self.body = deque([(11, 10), (10, 10), (9, 10)])
        # Il set contiene i segmenti del corpo, esclusa la testa
        self.body_set = {segment for segment in list(self.body)[1:]}
        self.direction = (1, 0)
        self.grow = False

    def get_head_position(self):
        """Restituisce la posizione attuale della testa del serpente."""
        return self.body[0]

    def move(self):
        """
        Aggiorna la posizione del serpente in base alla direzione corrente.
        Gestisce la crescita e aggiorna il set che tiene traccia delle posizioni occupate.
        """
        new_head = (self.body[0][0] + self.direction[0],
                    self.body[0][1] + self.direction[1])
        if self.grow:
            self.body.appendleft(new_head)
            # Il vecchio head diventa parte del corpo
            self.body_set.add(self.body[1])
            self.grow = False
        else:
            self.body.appendleft(new_head)
            tail = self.body.pop()
            if tail in self.body_set:
                self.body_set.remove(tail)
            self.body_set.add(self.body[1])
        # Assicuriamoci che la testa non sia considerata nel body_set
        self.body_set.discard(new_head)

    def check_collision(self):
        """
        Controlla se il serpente ha colliso con se stesso o con i bordi della griglia.
        Restituisce True in caso di collisione, altrimenti False.
        """
        head = self.body[0]
        # Controllo dei bordi
        if not (0 <= head[0] < CELL_NUMBER and 0 <= head[1] < CELL_NUMBER):
            return True
        # Controllo collisione con il corpo
        return head in self.body_set


def heuristic(a, b):
    """
    Funzione euristica per l'algoritmo A* (distanza Manhattan).
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def a_star(start, target, obstacles):
    """
    Algoritmo A* per calcolare il percorso dal punto start al target evitando gli ostacoli.
    
    :param start: Posizione iniziale (tupla).
    :param target: Posizione di destinazione (tupla).
    :param obstacles: Insieme di posizioni che rappresentano ostacoli.
    :return: Lista di posizioni che compongono il percorso (senza includere la posizione di partenza),
             oppure una lista vuota se il percorso non esiste.
    """
    try:
        queue = []
        heapq.heappush(queue, (0, start))
        came_from = {}
        cost_so_far = {start: 0}
        obstacles_set = set(obstacles)

        while queue:
            current = heapq.heappop(queue)[1]
            if current == target:
                break

            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if (0 <= neighbor[0] < CELL_NUMBER and
                    0 <= neighbor[1] < CELL_NUMBER and
                    neighbor not in obstacles_set):

                    new_cost = cost_so_far[current] + 1
                    if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                        cost_so_far[neighbor] = new_cost
                        priority = new_cost + heuristic(target, neighbor)
                        heapq.heappush(queue, (priority, neighbor))
                        came_from[neighbor] = current
        else:
            # Se il ciclo termina senza aver raggiunto il target
            return []

        # Ricostruzione del percorso
        path = []
        current = target
        while current != start:
            path.append(current)
            current = came_from.get(current)
            if current is None:
                logging.error("Percorso non valido trovato in A*")
                return []
        path.append(start)
        path.reverse()
        return path[1:]
    except Exception as e:
        logging.error(f"Errore in a_star: {e}")
        return []


def get_escape_targets(current_pos):
    """
    Restituisce le posizioni ai bordi della griglia per cercare vie di fuga.
    """
    x, y = current_pos
    return [
        (x, 0),
        (x, CELL_NUMBER - 1),
        (0, y),
        (CELL_NUMBER - 1, y)
    ]


def is_trapped(position, body):
    """
    Determina se, partendo da una data posizione, il serpente è intrappolato (non riesce a raggiungere
    nessun target di fuga).
    
    :param position: Posizione da cui partire.
    :param body: Corpo attuale del serpente.
    :return: True se intrappolato, False altrimenti.
    """
    virtual_body = [position] + list(body)[:-1]
    escape_targets = get_escape_targets(position)
    for target in escape_targets:
        if a_star(position, target, virtual_body):
            return False
    return True


def draw_snake(body):
    """
    Disegna il serpente sullo schermo.
    """
    for segment in body:
        x = segment[0] * CELL_SIZE
        y = segment[1] * CELL_SIZE
        snake_rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, SNAKE_COLOR, snake_rect)


def draw_food(pos):
    """
    Disegna il cibo sullo schermo.
    """
    x = pos[0] * CELL_SIZE
    y = pos[1] * CELL_SIZE
    food_rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
    pygame.draw.rect(screen, FOOD_COLOR, food_rect)


def draw_text(text, pos):
    """
    Disegna il testo specificato sullo schermo nella posizione indicata.
    """
    text_surface = font.render(text, True, TEXT_COLOR)
    screen.blit(text_surface, pos)


def generate_food(snake):
    """
    Genera una posizione valida per il cibo, evitando il corpo del serpente.
    
    :param snake: Istanza dell'oggetto Snake.
    :return: Tupla contenente le coordinate del cibo.
    :raises RuntimeError: se non è possibile trovare una posizione valida.
    """
    max_attempts = 1000
    attempts = 0
    while attempts < max_attempts:
        x = random.randint(0, CELL_NUMBER - 1)
        y = random.randint(0, CELL_NUMBER - 1)
        if (x, y) not in snake.body_set and (x, y) != snake.get_head_position():
            return (x, y)
        attempts += 1
    logging.error("Impossibile generare una posizione valida per il cibo dopo numerosi tentativi.")
    raise RuntimeError("Spazio esaurito per generare il cibo.")


def handle_events(snake, auto_mode, game_over, paused):
    """
    Gestisce gli eventi di input, aggiornando lo stato del gioco.
    
    :param snake: Istanza di Snake.
    :param auto_mode: Modalità automatica attiva o meno.
    :param game_over: Stato del gioco (game over o meno).
    :param paused: Stato di pausa.
    :return: Tuple (running, auto_mode, game_over, paused, restart)
             dove 'restart' è True se è stato premuto il tasto di restart.
    """
    running = True
    restart = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            if not auto_mode and not game_over:
                if event.key == pygame.K_UP and snake.direction != (0, 1):
                    snake.direction = (0, -1)
                elif event.key == pygame.K_DOWN and snake.direction != (0, -1):
                    snake.direction = (0, 1)
                elif event.key == pygame.K_LEFT and snake.direction != (1, 0):
                    snake.direction = (-1, 0)
                elif event.key == pygame.K_RIGHT and snake.direction != (-1, 0):
                    snake.direction = (1, 0)

            if event.key == pygame.K_m:
                auto_mode = not auto_mode

            if event.key == pygame.K_r and game_over:
                # Segnaliamo il restart: il reset dello snake e la generazione del cibo
                restart = True
                game_over = False

            if event.key == pygame.K_p:
                paused = not paused
    return running, auto_mode, game_over, paused, restart


def main():
    """
    Funzione principale che gestisce il ciclo del gioco.
    """
    snake = Snake()
    try:
        food_pos = generate_food(snake)
    except RuntimeError as e:
        logging.critical("Errore durante la generazione iniziale del cibo. Uscita dal gioco.")
        sys.exit(1)

    # Questi parametri ora persistono anche dopo il restart
    game_speed = 10
    auto_mode = True
    game_over = False
    paused = False
    score = 0
    running = True

    while running:
        # Gestione degli eventi
        try:
            running, auto_mode, game_over, paused, restart = handle_events(snake, auto_mode, game_over, paused)
        except Exception as e:
            logging.error(f"Errore durante la gestione degli eventi: {e}")
            continue

        # Se è stato richiesto un restart (premuto R in game over)
        if restart:
            snake.reset()
            try:
                food_pos = generate_food(snake)
            except RuntimeError as e:
                logging.error(e)
                game_over = True  # Se non riesce a generare il cibo, segnala game over
            # NOTA: score e game_speed rimangono invariati
            logging.info("Restart del gioco effettuato. Score e velocità mantengono i valori precedenti.")

        # Se il gioco è in pausa o in stato di game over, mostriamo le informazioni senza aggiornare la logica
        if game_over or paused:
            screen.fill(BACKGROUND_COLOR)
            draw_snake(snake.body)
            draw_food(food_pos)
            mode_text = "Auto" if auto_mode else "Manuale"
            draw_text(f"Score: {score} | Speed: {game_speed} | Mode: {mode_text}", (10, 10))
            if game_over:
                draw_text(f"Final Score: {score}", (WINDOW_SIZE // 3, WINDOW_SIZE // 2 - 40))
                draw_text("Game Over! Premi R per riavviare", (WINDOW_SIZE // 4, WINDOW_SIZE // 2))
                draw_text("oppure ESC per uscire", (WINDOW_SIZE // 3, WINDOW_SIZE // 2 + 40))
            elif paused:
                draw_text("Gioco in pausa. Premi P per riprendere.", (WINDOW_SIZE // 4, WINDOW_SIZE // 2))
            pygame.display.update()
            clock.tick(game_speed)
            continue

        # Logica della modalità automatica
        if auto_mode:
            try:
                path = a_star(snake.get_head_position(), food_pos, snake.body_set)
            except Exception as e:
                logging.error(f"Errore nel calcolo del percorso: {e}")
                path = []

            if not path:
                # Se non c'è percorso verso il cibo, tenta vie di fuga verso i bordi
                escape_targets = get_escape_targets(snake.get_head_position())
                best_path = []
                for target in escape_targets:
                    temp_path = a_star(snake.get_head_position(), target, snake.body_set)
                    if temp_path and (not best_path or len(temp_path) > len(best_path)):
                        best_path = temp_path

                if best_path:
                    path = best_path
                else:
                    # Cerca direzioni sicure basandosi sullo spazio futuro
                    safe_directions = []
                    for d in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        new_pos = (snake.get_head_position()[0] + d[0],
                                   snake.get_head_position()[1] + d[1])
                        if (new_pos not in snake.body_set and
                            0 <= new_pos[0] < CELL_NUMBER and
                            0 <= new_pos[1] < CELL_NUMBER):
                            future_path = a_star(new_pos, (CELL_NUMBER // 2, CELL_NUMBER // 2),
                                                 snake.body_set.union({new_pos}))
                            future_space = len(future_path) if future_path else 0
                            safe_directions.append((d, future_space))

                    if safe_directions:
                        safe_directions.sort(key=lambda x: (-x[1],
                                                             heuristic((snake.get_head_position()[0] + x[0][0],
                                                                        snake.get_head_position()[1] + x[0][1]),
                                                                       (CELL_NUMBER // 2, CELL_NUMBER // 2))))
                        snake.direction = safe_directions[0][0]
                    else:
                        logging.info("Nessuna direzione sicura trovata. Game Over.")
                        game_over = True

            if path:
                next_pos = path[0]
                dx = next_pos[0] - snake.get_head_position()[0]
                dy = next_pos[1] - snake.get_head_position()[1]
                # Verifica che la prossima mossa non intrappoli il serpente
                if not is_trapped(next_pos, snake.body):
                    snake.direction = (dx, dy)

        # Movimento del serpente
        try:
            snake.move()
        except Exception as e:
            logging.error(f"Errore nel movimento del serpente: {e}")
            game_over = True

        # Gestione della collisione con il cibo
        if snake.get_head_position() == food_pos:
            snake.grow = True
            try:
                food_pos = generate_food(snake)
            except RuntimeError as e:
                logging.error(e)
                game_over = True
            score += 1
            game_speed = min(game_speed + 1, 50)

        # Verifica collisione (con se stesso o bordi)
        if snake.check_collision():
            game_over = True

        # Aggiornamento grafico
        screen.fill(BACKGROUND_COLOR)
        draw_snake(snake.body)
        draw_food(food_pos)
        mode_text = "Auto" if auto_mode else "Manuale"
        draw_text(f"Score: {score} | Speed: {game_speed} | Mode: {mode_text}", (10, 10))
        if game_over:
            draw_text(f"Final Score: {score}", (WINDOW_SIZE // 3, WINDOW_SIZE // 2 - 40))
            draw_text("Game Over! Premi R per riavviare", (WINDOW_SIZE // 4, WINDOW_SIZE // 2))
            draw_text("oppure ESC per uscire", (WINDOW_SIZE // 3, WINDOW_SIZE // 2 + 40))

        pygame.display.update()
        clock.tick(game_speed)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Errore critico nell'applicazione: {e}")
        pygame.quit()
        sys.exit(1)
