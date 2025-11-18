import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.util.ArrayList;
import java.util.Random;
import javax.sound.sampled.*;
import java.io.File;

public class MarioGame extends JFrame implements Runnable, KeyListener {
    private static final int WIDTH = 800;
    private static final int HEIGHT = 600;
    private Player mario;
    private Level currentLevel;
    private boolean[] keys;
    private int currentLevelNumber = 1;
    private int lives = 3;
    private boolean paused = false;
    private long startTime = System.currentTimeMillis();
    
    public MarioGame() {
        setTitle("Super Mario Bros");
        setSize(WIDTH, HEIGHT);
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        addKeyListener(this);
        keys = new boolean[256];
        initializeGame();
    }
    
    private void initializeGame() {
        mario = new Player(100, 500);
        loadLevel(currentLevelNumber);
        new Thread(this).start();
    }
    
    private void loadLevel(int levelNumber) {
        currentLevel = new Level(levelNumber);
    }

    public void run() {
        final int FPS = 60;
        final long OPTIMAL_TIME = 1_000_000_000 / FPS;
        long lastTime = System.nanoTime();

        while (true) {
            long now = System.nanoTime();
            long delta = now - lastTime;

            if (delta >= OPTIMAL_TIME) {
                gameUpdate();
                repaint();
                lastTime = now;
            }

            // Reducir uso de CPU
            try {
                Thread.sleep(1);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
    
    private void gameUpdate() {
        if (paused) return;
        handleInput();
        mario.update(currentLevel.getPlatforms(), currentLevel.getEnemies());
        currentLevel.updateEnemies();
        checkCollisions();
        checkLevelCompletion();
    }
    
    private void handleInput() {
        if (keys[KeyEvent.VK_LEFT]) mario.moveLeft();
        if (keys[KeyEvent.VK_RIGHT]) mario.moveRight();
        if (keys[KeyEvent.VK_SPACE]) {
            mario.jump();
            Sound.playSound("jump.wav");
        }
    }
    
    private void checkCollisions() {
        for (Enemy enemy : currentLevel.getEnemies()) {
            if (mario.getBounds().intersects(enemy.getBounds())) {
                if (mario.isJumping()) {
                    enemy.defeat();
                    mario.gainXP(enemy.getXpValue());
                } else {
                    mario.takeDamage(enemy.getDamage());
                    if (mario.getHealth() <= 0) {
                        lives--;
                        if (lives <= 0) {
                            int option = JOptionPane.showConfirmDialog(this, "¡Game Over! ¿Quieres reiniciar?", "Game Over", JOptionPane.YES_NO_OPTION);
                            if (option == JOptionPane.YES_OPTION) {
                                restartGame();
                            } else {
                                System.exit(0);
                            }
                        } else {
                            mario.resetPosition();
                        }
                    }
                }
            }
        }
    }

    private void restartGame() {
        lives = 3;
        currentLevelNumber = 1;
        initializeGame();
    }
    
    private void checkLevelCompletion() {
        if (currentLevel.isCompleted()) {
            currentLevelNumber++;
            if (currentLevelNumber > 10) {
                // Juego completado
            } else {
                loadLevel(currentLevelNumber);
                mario.resetPosition();
            }
        }
    }

    public void paint(Graphics g) {
        Image buffer = createImage(WIDTH, HEIGHT);
        Graphics bg = buffer.getGraphics();
        drawGame(bg);
        g.drawImage(buffer, 0, 0, this);
    }
    
    private void drawGame(Graphics g) {
        // Dibujar fondo
        g.setColor(Color.CYAN);
        g.fillRect(0, 0, WIDTH, HEIGHT);
        
        // Dibujar nivel
        currentLevel.draw(g);
        
        // Dibujar jugador
        mario.draw(g);
        
        // Dibujar HUD
        drawHUD(g);
    }
    
    private void drawHUD(Graphics g) {
        g.setColor(Color.BLACK);
        g.drawString("Nivel: " + currentLevelNumber, 20, 20);
        g.drawString("HP: " + mario.getHealth(), 20, 40);
        g.drawString("XP: " + mario.getXp() + "/" + mario.getNextLevelXP(), 20, 60);
        g.drawString("Vidas: " + lives, 20, 80);

        // Mostrar tiempo restante
        long elapsedTime = (System.currentTimeMillis() - startTime) / 1000;
        g.drawString("Tiempo: " + elapsedTime + "s", 20, 100);
    }

    // KeyListener methods
    public void keyPressed(KeyEvent e) {
        if (e.getKeyCode() == KeyEvent.VK_P) {
            paused = !paused;
        }
        keys[e.getKeyCode()] = true;
    }
    public void keyReleased(KeyEvent e) { keys[e.getKeyCode()] = false; }
    public void keyTyped(KeyEvent e) {}

    public static void main(String[] args) {
        new MarioGame().setVisible(true);
    }
}

class Player {
    private int x, y;
    private int health = 100;
    private int xp = 0;
    private int level = 1;
    private int attack = 10;
    private int defense = 5;
    private int speed = 5;
    private boolean jumping = false;
    private Image walkSprite;
    private Image jumpSprite;
    
    public Player(int x, int y) {
        this.x = x;
        this.y = y;

        try {
            walkSprite = Toolkit.getDefaultToolkit().getImage("walk.png");
            jumpSprite = Toolkit.getDefaultToolkit().getImage("jump.png");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    
    public void update(ArrayList<Platform> platforms, ArrayList<Enemy> enemies) {
        // Aplicar gravedad
        y += 5;

        // Verificar colisiones con plataformas
        for (Platform platform : platforms) {
            if (getBounds().intersects(platform.getBounds())) {
                if (y + getHeight() <= platform.getY() + 5) { // Aterrizaje
                    y = platform.getY() - getHeight();
                    jumping = false;
                }
            }
        }
    }
    
    public void draw(Graphics g) {
        Image sprite = jumping ? jumpSprite : walkSprite;
        g.drawImage(sprite, x, y, null);
    }
    
    private void levelUp() {
        xp += level * 100;
        health += 20 + (level * 2);
        attack += 5 + (level * 1);
        defense += 3 + (level * 1);
        speed += 1;
    }
    
    public void gainXP(int amount) {
        xp += amount;
        if (xp >= getNextLevelXP()) {
            level++;
            levelUp();
        }
    }
    
    public int getNextLevelXP() {
        return level * 100;
    }
    
    // Resto de métodos (movimiento, daño, dibujo, etc.)
}

abstract class Enemy {
    protected int x, y;
    protected int health;
    protected int damage;
    protected int speed;
    protected int xpValue;
       
    public abstract void update();
    public abstract void draw(Graphics g);
    
    public void defeat() {
        health = 0;
    }
    
    // Getters y setters
}

// Ejemplo de enemigos específicos
class Goomba extends Enemy {
    public Goomba(int x, int y) {
        this.x = x;
        this.y = y;
        health = 10;
        damage = 5;
        speed = 2;
        xpValue = 20;
    }
    
    public void update() {
        // Movimiento simple
        x += speed;
    }
    
    public void draw(Graphics g) {
        g.setColor(Color.RED);
        g.fillRect(x, y, 30, 30);
    }
}

// Implementar otros 9 tipos de enemigos...

class Level {
    private int levelNumber;
    private ArrayList<Platform> platforms = new ArrayList<>();
    private ArrayList<Enemy> enemies = new ArrayList<>();
    
    public Level(int number) {
        this.levelNumber = number;
        generateLevel();
    }
    
    private void generateLevel() {
        platforms.add(new Platform(0, 550, 800, 50)); // Suelo

        Random rand = new Random();
        for (int i = 0; i < levelNumber * 2; i++) {
            int x = rand.nextInt(700) + 50;
            int y = rand.nextInt(400) + 100;
            platforms.add(new Platform(x, y, 100, 20));
        }

        for (int i = 0; i < levelNumber * 2; i++) {
            int x = rand.nextInt(700) + 50;
            int y = 500;
            enemies.add(new Goomba(x, y));
        }
    }
    
    public void updateEnemies() {
        enemies.removeIf(e -> ((Enemy)e).getHealth() <= 0);
        enemies.forEach(Enemy::update);
    }
    
    // Resto de métodos (dibujo, obtención de plataformas, etc.)
}

class Platform {
    private int x, y, width, height;
    
    public Platform(int x, int y, int width, int height) {
        this.x = x;
        this.y = y;
        this.width = width;
        this.height = height;
    }
    
    // Getters y método de dibujo
}

class Sound {
    public static void playSound(String filePath) {
        try {
            AudioInputStream audio = AudioSystem.getAudioInputStream(new File(filePath));
            Clip clip = AudioSystem.getClip();
            clip.open(audio);
            clip.start();
        } catch (Exception e) {
            System.err.println("Error al reproducir el sonido: " + filePath);
        }
    }
}