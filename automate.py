import asyncio, json, random, websockets, pygame, sys

# --- CONFIGURATION SYSTÈME ---
sys.setrecursionlimit(5000)

# --- CONFIGURATION ARCHIPELAGO ---
ITEM_ID_TO_NAME = {
    60001: "Puce de Mouvement", 60002: "Epee", 60003: "Masque a Gaz", 
    60004: "Potion", 60005: "Puce de Gauche", 60006: "Puce de Recul", 
    60007: "Boussole", 60012: "Clef Etage 1", 
    60008: "Clef Etage 2", 60009: "Clef Etage 3", 60010: "Clef Etage 4", 60011: "Clef Etage 5"
}

# IDs de 70001 à 70005 pour les niveaux, 70006+ pour les coffres, 70021 cadeau, 70030+ ennemis
LOCATION_NAME_TO_ID = {
    "Cadeau de l'Alchimiste": 70021,
    **{f"Niveau {i}": 70000 + i for i in range(1, 6)},
    **{f"Coffre {c} Etage {i}": 70005 + ((i-1)*3) + c for i in range(1, 6) for c in range(1, 4)},
    **{f"Ennemi {e} Etage {i}": 70030 + ((i-1)*4) + e for i in range(1, 6) for e in range(1, 5)}
}

# --- ÉTAT DU JEU ---
labyrinthe = []
robot_pos = [1, 1]
direction = (1, 0)
liste_ennemis = [] 
niveau = 1
pv = 10
nombre_potions = 0
inventaire_joueur = set()
coffres_restants = 0
coffres_totaux_niveau = 0
socket = None
running = True
etat_jeu = "MENU"
log_messages = []
vitesse_reelle = 0.25
TAILLE_GRILLE = 13
CELL_SIZE = 35
OFFSET_X, OFFSET_Y = 50, 50

# --- CONFIGURATION UI MENU ---
SERVER_ADDRESS = "127.0.0.1:38281"
SLOT_NAME = "Jerome"
VITESSE_SAISIE = "5"
GAME_NAME = "Alchimiste"

input_rect_server = pygame.Rect(300, 120, 250, 35)
input_rect_name = pygame.Rect(300, 190, 250, 35)
input_rect_speed = pygame.Rect(300, 260, 250, 35)
active_input = "server"
msg_erreur = ""

# --- INITIALISATION PYGAME ---
pygame.init()
LARG, HAUT = 850, 600
screen = pygame.display.set_mode((LARG, HAUT))
pygame.display.set_caption("L'Automate Alchimiste - Archipelago")
font = pygame.font.SysFont("Verdana", 18)
font_titre = pygame.font.SysFont("Verdana", 32, bold=True)

# --- GÉNÉRATEUR ---
def generer_niveau(taille, num_niveau):
    global liste_ennemis
    grille = [[1 for _ in range(taille)] for _ in range(taille)]
    def creuser(x, y):
        grille[y][x] = 0
        dirs = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 < nx < taille-1 and 0 < ny < taille-1 and grille[ny][nx] == 1:
                grille[y + dy//2][x + dx//2] = 0
                creuser(nx, ny)
    creuser(1, 1)
    
    culs = []
    for y in range(1, taille-1):
        for x in range(1, taille-1):
            if grille[y][x] == 0 and (x,y) != (1,1):
                if sum([1 for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)] if grille[y+dy][x+dx]==1]) == 3:
                    culs.append((x,y))
    if culs:
        culs.sort(key=lambda p: (p[0]-1)+(p[1]-1), reverse=True)
        grille[culs[0][1]][culs[0][0]] = 2 
    else: grille[taille-2][taille-2] = 2

    chemins = [(x,y) for y in range(taille) for x in range(taille) if grille[y][x]==0 and (x,y)!=(1,1) and grille[y][x]!=2]
    
    nb_c = 0
    for _ in range(3):
        if chemins:
            cx, cy = random.choice(chemins)
            grille[cy][cx] = 4; nb_c += 1; chemins.remove((cx,cy))
    
    liste_ennemis = []
    nb_e = (num_niveau // 2) + 2
    for i in range(1, nb_e + 1):
        if chemins:
            ex, ey = random.choice(chemins)
            grille[ey][ex] = 3
            liste_ennemis.append({"pos": [ex, ey], "id": i})
            chemins.remove((ex,ey))

    for _ in range(num_niveau):
        if chemins:
            px, py = random.choice(chemins)
            grille[py][px] = 5; chemins.remove((px,py))

    return grille, nb_c

def choisir_direction():
    global direction
    x, y = robot_pos
    dx, dy = direction
    cle = f"Clef Etage {niveau}"
    def ok(tx, ty):
        if not (0 <= tx < TAILLE_GRILLE and 0 <= ty < TAILLE_GRILLE): return False
        v = labyrinthe[ty][tx]
        return v != 1 and (v != 5 or cle in inventaire_joueur)
    
    if ok(x-dy, y+dx): direction = (-dy, dx)
    elif ok(x+dx, y+dy): pass
    elif "Puce de Gauche" in inventaire_joueur and ok(x+dy, y-dx): direction = (dy, -dx)
    elif "Puce de Recul" in inventaire_joueur: direction = (-dx, -dy)

# --- DESSIN ---
def dessiner_menu():
    screen.fill((30, 30, 40))
    txt = font_titre.render("L'Automate Alchimiste", True, (0, 200, 255))
    screen.blit(txt, (LARG//2 - txt.get_width()//2, 40))
    champs = [("Serveur :", input_rect_server, SERVER_ADDRESS, "server"),
              ("Pseudo :", input_rect_name, SLOT_NAME, "name"),
              ("Vitesse (1-10) :", input_rect_speed, VITESSE_SAISIE, "speed")]
    for label, rect, val, name in champs:
        color = (255, 255, 255) if active_input == name else (150, 150, 150)
        pygame.draw.rect(screen, color, rect, 2)
        screen.blit(font.render(label, True, (200, 200, 200)), (rect.x, rect.y - 22))
        screen.blit(font.render(val, True, (255, 255, 255)), (rect.x + 8, rect.y + 8))
    pygame.draw.rect(screen, (0, 120, 200), (350, 340, 150, 50), border_radius=10)
    screen.blit(font.render("CONNECTER", True, (255, 255, 255)), (365, 352))
    if msg_erreur: screen.blit(font.render(msg_erreur, True, (255, 100, 100)), (LARG//2 - 120, 420))
    pygame.display.flip()

def dessiner_jeu():
    fond = (20, 40, 20) if (niveau == 3 and "Masque a Gaz" not in inventaire_joueur) else (20, 20, 25)
    screen.fill(fond)
    for y in range(TAILLE_GRILLE):
        for x in range(TAILLE_GRILLE):
            rect = (OFFSET_X + x*CELL_SIZE, OFFSET_Y + y*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            v = labyrinthe[y][x]
            if v == 1: pygame.draw.rect(screen, (50, 50, 60), rect)
            elif v == 2:
                col = (255, 215, 0) if "Boussole" in inventaire_joueur else (35, 35, 40)
                pygame.draw.rect(screen, col, rect)
            elif v == 3: pygame.draw.circle(screen, (255, 50, 50), (int(rect[0]+CELL_SIZE/2), int(rect[1]+CELL_SIZE/2)), int(CELL_SIZE/3))
            elif v == 4: pygame.draw.rect(screen, (0, 191, 255), rect)
            elif v == 5: pygame.draw.rect(screen, (139, 69, 19), rect); pygame.draw.rect(screen, (255, 255, 0), rect, 2)
            pygame.draw.rect(screen, (35, 35, 40), rect, 1)
    
    rx, ry = OFFSET_X+robot_pos[0]*CELL_SIZE+CELL_SIZE/2, OFFSET_Y+robot_pos[1]*CELL_SIZE+CELL_SIZE/2
    pygame.draw.circle(screen, (0, 180, 255), (int(rx), int(ry)), int(CELL_SIZE/3))
    pygame.draw.rect(screen, (0, 200, 80), (550, 50, pv * 20, 20))
    screen.blit(font.render(f"ÉTAGE : {niveau}", True, (255,255,255)), (550, 80))
    screen.blit(font.render(f"COFFRES : {coffres_restants}", True, (255,100,100) if coffres_restants > 0 else (0,255,0)), (550, 110))
    screen.blit(font.render(f"🧪 POTIONS : {nombre_potions}", True, (200, 200, 255)), (550, 140))
    y_inv = 180
    items = ["Epee", "Masque a Gaz", "Puce de Gauche", "Puce de Recul", "Boussole", f"Clef Etage {niveau}"]
    for p in items:
        col = (0, 255, 0) if p in inventaire_joueur else (100, 100, 100)
        screen.blit(font.render(p, True, col), (550, y_inv)); y_inv += 25
    pygame.draw.rect(screen, (140, 0, 0), (650, 530, 160, 45), border_radius=10)
    screen.blit(font.render("QUITTER", True, (255, 255, 255)), (685, 540))
    if log_messages: screen.blit(font.render(f"> {log_messages[-1]}", True, (0, 255, 0)), (20, 560))
    pygame.display.flip()

# --- RÉSEAU ---
async def ecouter_serveur():
    global inventaire_joueur, nombre_potions, socket, running
    try:
        while running and socket:
            data = json.loads(await socket.recv())
            for pkt in data:
                if pkt["cmd"] == "ReceivedItems":
                    for item in pkt["items"]:
                        nom = ITEM_ID_TO_NAME.get(item["item"], "Objet")
                        if nom == "Potion": nombre_potions += 1
                        else: inventaire_joueur.add(nom)
                        log_messages.append(f"Reçu : {nom}")
    except: pass

async def tentative_connexion():
    global socket, etat_jeu, msg_erreur, labyrinthe, coffres_restants, vitesse_reelle, TAILLE_GRILLE, CELL_SIZE, ecouteur_tache
    try:
        try: v = float(VITESSE_SAISIE); vitesse_reelle = max(0.05, 1.0 / max(0.1, v))
        except: vitesse_reelle = 0.25
        ws = await websockets.connect(f"ws://{SERVER_ADDRESS.strip()}", open_timeout=5)
        await ws.send(json.dumps([{"cmd":"Connect","password":"","game":GAME_NAME,"name":SLOT_NAME,"uuid":"bot_vFinal","version":{"major":0,"minor":5,"build":0,"class":"Version"},"items_handling":7,"tags":[]}]))
        while True:
            res = json.loads(await ws.recv())
            for p in res:
                if p["cmd"] == "Connected":
                    socket = ws; TAILLE_GRILLE = 13 + (niveau-1)*4; CELL_SIZE = 450 // TAILLE_GRILLE
                    labyrinthe, coffres_restants = generer_niveau(TAILLE_GRILLE, niveau)
                    etat_jeu = "JEU"; ecouteur_tache = asyncio.create_task(ecouter_serveur())
                    await socket.send(json.dumps([{"cmd": "LocationChecks", "locations": [70021]}])) # Cadeau
                    return
            await asyncio.sleep(0.1)
    except Exception as e: msg_erreur = f"Erreur : {e}"

# --- MAIN ---
async def main():
    global running, etat_jeu, robot_pos, direction, pv, niveau, labyrinthe, coffres_restants, TAILLE_GRILLE, CELL_SIZE, nombre_potions, SERVER_ADDRESS, SLOT_NAME, VITESSE_SAISIE, active_input, liste_ennemis, log_messages, vitesse_reelle
    while running:
        if etat_jeu == "MENU":
            dessiner_menu()
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if input_rect_server.collidepoint(event.pos): active_input = "server"
                    elif input_rect_name.collidepoint(event.pos): active_input = "name"
                    elif input_rect_speed.collidepoint(event.pos): active_input = "speed"
                    elif pygame.Rect(350, 340, 150, 50).collidepoint(event.pos): await tentative_connexion()
                if event.type == pygame.KEYDOWN:
                    if active_input == "server": target = SERVER_ADDRESS
                    elif active_input == "name": target = SLOT_NAME
                    else: target = VITESSE_SAISIE
                    if event.key == pygame.K_BACKSPACE: target = target[:-1]
                    elif event.unicode.isprintable(): target += event.unicode
                    if active_input == "server": SERVER_ADDRESS = target
                    elif active_input == "name": SLOT_NAME = target
                    else: VITESSE_SAISIE = target
            await asyncio.sleep(0.05)
        else:
            dessiner_jeu()
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if event.type == pygame.MOUSEBUTTONDOWN and 650 <= event.pos[0] <= 810 and 530 <= event.pos[1] <= 575: running = False
            await asyncio.sleep(vitesse_reelle)
            
            if "Puce de Mouvement" in inventaire_joueur:
                for i in range(len(liste_ennemis)):
                    if random.random() < 0.2:
                        ex, ey = liste_ennemis[i]["pos"]
                        move = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
                        nx, ny = ex+move[0], ey+move[1]
                        if 0<=ny<TAILLE_GRILLE and 0<=nx<TAILLE_GRILLE and labyrinthe[ny][nx] == 0:
                            labyrinthe[ey][ex] = 0; liste_ennemis[i]["pos"] = [nx, ny]; labyrinthe[ny][nx] = 3

                if pv <= 4 and nombre_potions > 0: pv = min(10, pv+5); nombre_potions -= 1; log_messages.append("🧪 Potion !")
                if pv <= 0: pv, robot_pos, direction = 10, [1,1], (1,0); log_messages.append("Réparation..."); continue
                
                choisir_direction(); nx, ny = robot_pos[0]+direction[0], robot_pos[1]+direction[1]
                if labyrinthe[ny][nx] == 5:
                    if f"Clef Etage {niveau}" in inventaire_joueur: labyrinthe[ny][nx] = 0; log_messages.append("Porte ouverte !")
                    else: continue
                if labyrinthe[ny][nx] != 1:
                    robot_pos = [nx, ny]; case = labyrinthe[ny][nx]
                    if case == 4:
                        c_idx = 3 - coffres_restants + 1
                        lid = LOCATION_NAME_TO_ID.get(f"Coffre {c_idx} Etage {niveau}")
                        if lid: await socket.send(json.dumps([{"cmd":"LocationChecks","locations":[lid]}]))
                        labyrinthe[ny][nx], coffres_restants = 0, coffres_restants - 1; log_messages.append("Coffre !")
                    if case == 3:
                        for e in liste_ennemis:
                            if e["pos"] == [nx, ny]:
                                lid = LOCATION_NAME_TO_ID.get(f"Ennemi {e['id']} Etage {niveau}")
                                if lid: await socket.send(json.dumps([{"cmd":"LocationChecks","locations":[lid]}]))
                                break
                        if "Epee" in inventaire_joueur: labyrinthe[ny][nx] = 0; log_messages.append("Ennemi vaincu !")
                        else: pv -= random.randint(2,4); log_messages.append("Dégâts !")
                        liste_ennemis = [e for e in liste_ennemis if e["pos"] != [nx, ny]]
                    if niveau == 3 and "Masque a Gaz" not in inventaire_joueur: pv -= 1
                    if case == 2:
                        if coffres_restants <= 0:
                            lid = LOCATION_NAME_TO_ID.get(f"Niveau {niveau}")
                            await socket.send(json.dumps([{"cmd":"LocationChecks","locations":[lid]}]))
                            if niveau >= 5:
                                await socket.send(json.dumps([{"cmd":"StatusUpdate","status":30}]))
                                log_messages.append("VICTOIRE !"); await asyncio.sleep(3); running = False
                            else:
                                niveau += 1; TAILLE_GRILLE = 13+(niveau-1)*4; CELL_SIZE = 450 // TAILLE_GRILLE
                                labyrinthe, coffres_restants = generer_niveau(TAILLE_GRILLE, niveau); robot_pos, direction = [1,1], (1,0)
                        else:
                            if not any("verrouillée" in m for m in log_messages[-1:]): log_messages.append("Porte verrouillée !")
    pygame.quit(); sys.exit()

if __name__ == "__main__": asyncio.run(main())